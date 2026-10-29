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
from estalvia.engine.errors import EngineError
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


MWH_A_KWH = Decimal(1000)  # la serie de mercado va en EUR/MWh (VERIFICAR la unidad)
AVISO_CAPACIDAD_P3 = ("el pago por capacidad de 2.0TD no tiene valor en P3 en el BOE (casilla en blanco): se toma 0 "
                      "(VERIFICAR)")
AVISO_SIN_AJUSTES = ("la oferta no declara servicios de ajuste ni otros costes variables: no se incluyen y el coste "
                     "real será algo mayor")


def _sin_pago_por_capacidad(tarifa: str, p: str) -> bool:
    """El BOE (Orden TED/1524/2025) deja en blanco el pago por capacidad de P3 en 2.0TD. Es el único hueco que se
    interpreta como 0 (VERIFICAR); cualquier otra regla que falte es un error, no un 0."""
    return tarifa == "2.0TD" and p == "P3"


def _regulado_eur_kwh(reglas: RuleSet, tarifa: str, periodo: Periodo, p: str) -> Decimal:
    """Peaje + cargo + pago por capacidad de energía del periodo tarifario."""
    total = Decimal(0)
    for kind in ("peaje_energia_eur_kwh", "cargo_energia_eur_kwh", "pago_capacidad_eur_kwh"):
        if kind == "pago_capacidad_eur_kwh" and _sin_pago_por_capacidad(tarifa, p):
            continue
        r0, r1 = reglas.find(kind, periodo.inicio, tarifa, p), reglas.find(kind, periodo.fin, tarifa, p)
        if r0.id != r1.id:
            raise FaltaDato(f"la regla {kind} del periodo {p} cambia dentro del periodo facturado")
        total += r0.value
    return total


def _precio_por_hora(mercado: PriceResult) -> dict[datetime, Decimal] | None:
    """EUR/MWh medio de cada hora UTC completa (media de sus cuartos de hora: consumo repartido por igual dentro de la
    hora, VERIFICAR). Una hora cuenta solo si trae todos sus instantes distintos. None: resolución no soportada."""
    hora = timedelta(hours=1)
    if not mercado.paso or mercado.paso > hora or hora % mercado.paso:
        return None
    por_hora = hora // mercado.paso
    grupos: dict[datetime, dict[datetime, Decimal]] = defaultdict(dict)
    for punto in mercado.puntos:
        grupos[punto.instante_utc.replace(minute=0, second=0, microsecond=0)][punto.instante_utc] = punto.eur_mwh
    return {h: sum(v.values(), Decimal(0)) / len(v) for h, v in grupos.items() if len(v) == por_hora}


def _evaluar_indexada(site: SiteParams, ingesta: Ingesta, calendario: Calendario, reglas: RuleSet, periodo: Periodo,
                      oferta: OfertaIndexada,
                      mercado: PriceResult | None) -> tuple[PrecioContrato, tuple[str, ...]] | str:
    """Precios por periodo tarifario (media horaria ponderada por el consumo) o el motivo por el que no se puede."""
    if mercado is None or not mercado.completo:
        return f"sin precios de mercado: {mercado.error if mercado and mercado.error else 'no disponibles'}"
    precio_hora = _precio_por_hora(mercado)
    if precio_hora is None:
        return f"resolución de los precios de mercado no soportada: {mercado.paso}"
    desde, hasta = limites_del_periodo(periodo)
    horas = [(x, p) for x, p in ingesta.etiquetadas(calendario, tarifa=site.tarifa) if desde <= x.instante_utc < hasta]
    faltan = sorted({x.instante_utc for x, _ in horas if x.instante_utc not in precio_hora})
    if faltan:
        return f"faltan precios de mercado de {len(faltan)} horas del periodo: no se rellenan"
    otros = oferta.otros_eur_kwh or Decimal(0)
    coste, kwh = defaultdict(Decimal), defaultdict(Decimal)
    for x, p in horas:
        coste[p] += x.kwh * (precio_hora[x.instante_utc] / MWH_A_KWH + oferta.margen_eur_kwh + otros)
        kwh[p] += x.kwh
    efectivo = {p: (coste[p] / kwh[p] if kwh[p] else Decimal(0)) + _regulado_eur_kwh(reglas, site.tarifa, periodo, p)
                for p in kwh}
    avisos = ((AVISO_CAPACIDAD_P3,) if any(_sin_pago_por_capacidad(site.tarifa, p) for p in kwh) else ()) + (
        (AVISO_SIN_AJUSTES,) if oferta.otros_eur_kwh is None else ())
    return PrecioContrato(efectivo, oferta.potencia_eur_kw_anio), avisos


def _sin_calcular(oferta: OfertaFija | OfertaIndexada, motivo: str, mercado: PriceResult | None) -> ResultadoOferta:
    es_fija = isinstance(oferta, OfertaFija)
    return ResultadoOferta(oferta.nombre, "fija" if es_fija else "indexada", oferta.capturada, None, None, False,
                           (motivo,), None if es_fija or not mercado else mercado.capturado_en,
                           None if es_fija or not mercado else mercado.atribucion)


def evaluar_oferta(site: SiteParams, ingesta: Ingesta, calendario: Calendario, reglas: RuleSet,
                   contrato: PrecioContrato, periodo: Periodo, oferta: OfertaFija | OfertaIndexada,
                   mercado: PriceResult | None = None) -> ResultadoOferta:
    """Recalcula la factura con la oferta y la compara con la línea base del contrato actual. Si la oferta no se puede
    calcular (falta un precio o una regla, o precios de mercado), el resultado sale marcado y sin importe."""
    base = linea_base(site, ingesta, calendario, reglas, contrato, periodo)
    kwh = consumo_por_periodo(site, ingesta, calendario, periodo)
    try:
        if isinstance(oferta, OfertaFija):
            precios, avisos = PrecioContrato(oferta.energia_eur_kwh, oferta.potencia_eur_kw_anio), ()
        else:
            calculo = _evaluar_indexada(site, ingesta, calendario, reglas, periodo, oferta, mercado)
            if isinstance(calculo, str):
                return _sin_calcular(oferta, calculo, mercado)
            precios, avisos = calculo
        total = desglose(site, kwh, reglas, precios, periodo).total
    except (FaltaDato, EngineError) as e:
        return _sin_calcular(oferta, f"no se puede calcular la oferta: {e}", mercado)
    es_fija = isinstance(oferta, OfertaFija)
    return ResultadoOferta(oferta.nombre, "fija" if es_fija else "indexada", oferta.capturada, total,
                           base.total - total, True, avisos, None if es_fija else mercado.capturado_en,
                           None if es_fija else mercado.atribucion)
