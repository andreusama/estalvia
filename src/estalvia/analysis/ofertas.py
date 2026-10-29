"""Ofertas de otras comercializadoras (spec #18, ticket #21): el motor las recalcula sobre el consumo real.

Una oferta entra solo como dato explícito (precios, fecha de captura y de dónde sale); aquí no se busca ni se supone
ninguna. Todo importe lo calcula el motor: una oferta se traduce a precio por periodo tarifario y se recalcula
la factura.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from estalvia.analysis.nucleo import (
    FaltaDato,
    PrecioContrato,
    consumo_por_periodo,
    desglose,
    limites_del_periodo,
    linea_base,
)
from estalvia.engine.calc import Periodo, SiteParams
from estalvia.engine.errors import MissingRuleError
from estalvia.engine.periods import Calendario
from estalvia.engine.rules import RuleSet
from estalvia.ingestion.hourly import Ingesta
from estalvia.prices.store import PriceResult


@dataclass(frozen=True)
class OfertaFija:
    """Precio de energía por periodo, con peajes y cargos incluidos (como el de la factura del cliente)."""
    nombre: str
    energia_eur_kwh: dict[str, Decimal]
    potencia_eur_kw_anio: dict[str, Decimal]
    capturada: date  # el día en que se copió la oferta
    fuente: str  # de dónde sale (por ejemplo, el comparador de la CNMC y su enlace)


@dataclass(frozen=True)
class OfertaIndexada:
    """Precio de la energía = mercado de cada hora + margen + otros costes de la oferta; los peajes, cargos y pagos
    por capacidad son los regulados (`rules/`). Los servicios de ajuste no vienen del mercado: si la oferta no los
    declara (`otros_eur_kwh` es None) el resultado lo avisa y el coste real será algo mayor."""
    nombre: str
    margen_eur_kwh: Decimal
    potencia_eur_kw_anio: dict[str, Decimal]
    capturada: date
    fuente: str
    otros_eur_kwh: Decimal | None = None


@dataclass(frozen=True)
class ResultadoOferta:
    oferta: str
    tipo: Literal["fija", "indexada"]
    capturada: date
    total: Decimal | None  # None: no se pudo calcular (ver avisos); nunca se rellena
    ahorro: Decimal | None  # línea base menos total; negativo si la oferta sale más cara
    completo: bool
    avisos: tuple[str, ...] = ()
    precios_capturados_en: datetime | None = None  # captura de los precios de mercado (solo indexadas)
    atribucion: str | None = None


AVISO_SIN_AJUSTES = ("la oferta no declara servicios de ajuste ni otros costes variables: no se incluyen y el coste "
                     "real será algo mayor")


def _incompleto(oferta: OfertaIndexada, motivo: str, mercado: PriceResult | None) -> ResultadoOferta:
    return ResultadoOferta(oferta.nombre, "indexada", oferta.capturada, None, None, False, (motivo,),
                           mercado.capturado_en if mercado else None, mercado.atribucion if mercado else None)


def _regulado_eur_kwh(reglas: RuleSet, tarifa: str, periodo: Periodo, p: str) -> Decimal:
    """Peaje + cargo + pago por capacidad de energía del periodo tarifario. El pago por capacidad de 2.0TD no tiene
    valor en P3 (casilla en blanco en el BOE, VERIFICAR): sin regla se toma 0. Peaje y cargo son obligatorios."""
    total = Decimal(0)
    for kind, obligatoria in (("peaje_energia_eur_kwh", True), ("cargo_energia_eur_kwh", True),
                              ("pago_capacidad_eur_kwh", False)):
        try:
            r0 = reglas.find(kind, periodo.inicio, tarifa, p)
            r1 = reglas.find(kind, periodo.fin, tarifa, p)
        except MissingRuleError:
            if obligatoria:
                raise
            continue
        if r0.id != r1.id:
            raise FaltaDato(f"la regla {kind} del periodo {p} cambia dentro del periodo facturado")
        total += r0.value
    return total


def _precio_por_hora(mercado: PriceResult) -> tuple[dict[datetime, Decimal], int]:
    """EUR/MWh medio de cada hora UTC (media de sus cuartos de hora: consumo repartido por igual dentro de la hora,
    VERIFICAR) y cuántos puntos trae cada hora completa."""
    paso = mercado.paso or timedelta(hours=1)
    por_hora = int(timedelta(hours=1) / paso)
    grupos: dict[datetime, list[Decimal]] = defaultdict(list)
    for punto in mercado.puntos:
        grupos[punto.instante_utc.replace(minute=0, second=0, microsecond=0)].append(punto.eur_mwh)
    return {h: sum(v, Decimal(0)) / len(v) for h, v in grupos.items() if len(v) == por_hora}, por_hora


def _evaluar_indexada(site: SiteParams, ingesta: Ingesta, calendario: Calendario, reglas: RuleSet, periodo: Periodo,
                      oferta: OfertaIndexada,
                      mercado: PriceResult | None) -> tuple[PrecioContrato, tuple[str, ...]] | str:
    """Precios por periodo tarifario (media horaria ponderada por el consumo) o el motivo por el que no se puede."""
    if mercado is None or not mercado.completo:
        return f"sin precios de mercado: {mercado.error if mercado and mercado.error else 'no disponibles'}"
    precio_hora, _ = _precio_por_hora(mercado)
    desde, hasta = limites_del_periodo(periodo)
    horas = [(x, p) for x, p in ingesta.etiquetadas(calendario, tarifa=site.tarifa) if desde <= x.instante_utc < hasta]
    faltan = sorted({x.instante_utc for x, _ in horas if x.instante_utc not in precio_hora})
    if faltan:
        return f"faltan precios de mercado de {len(faltan)} horas del periodo: no se rellenan"
    otros = oferta.otros_eur_kwh or Decimal(0)
    coste, kwh = defaultdict(Decimal), defaultdict(Decimal)
    for x, p in horas:
        coste[p] += x.kwh * (precio_hora[x.instante_utc] / 1000 + oferta.margen_eur_kwh + otros)
        kwh[p] += x.kwh
    efectivo = {p: (coste[p] / kwh[p] if kwh[p] else Decimal(0)) + _regulado_eur_kwh(reglas, site.tarifa, periodo, p)
                for p in kwh}
    avisos = (AVISO_SIN_AJUSTES,) if oferta.otros_eur_kwh is None else ()
    return PrecioContrato(efectivo, oferta.potencia_eur_kw_anio), avisos


def evaluar_oferta(site: SiteParams, ingesta: Ingesta, calendario: Calendario, reglas: RuleSet,
                   contrato: PrecioContrato, periodo: Periodo, oferta: OfertaFija | OfertaIndexada,
                   mercado: PriceResult | None = None) -> ResultadoOferta:
    """Recalcula la factura con la oferta y la compara con la línea base del contrato actual."""
    base = linea_base(site, ingesta, calendario, reglas, contrato, periodo)
    kwh = consumo_por_periodo(site, ingesta, calendario, periodo)
    if isinstance(oferta, OfertaFija):
        total = desglose(site, kwh, reglas, PrecioContrato(oferta.energia_eur_kwh, oferta.potencia_eur_kw_anio),
                         periodo).total
        return ResultadoOferta(oferta.nombre, "fija", oferta.capturada, total, base.total - total, True)
    calculo = _evaluar_indexada(site, ingesta, calendario, reglas, periodo, oferta, mercado)
    if isinstance(calculo, str):
        return _incompleto(oferta, calculo, mercado)
    precios, avisos = calculo
    total = desglose(site, kwh, reglas, precios, periodo).total
    return ResultadoOferta(oferta.nombre, "indexada", oferta.capturada, total, base.total - total, True, avisos,
                           mercado.capturado_en, mercado.atribucion)
