"""Núcleo del análisis (spec #18): línea base y escenario de una factura 2.0TD.

Todo el cálculo lo hace el motor; aquí solo se juntan el consumo horario y los precios de la factura.
Si falta un precio o una hora de consumo se dice qué falta: nunca se estima ni se rellena.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from estalvia.engine.calc import Desglose, Lecturas, Periodo, SiteParams, calcular_factura
from estalvia.engine.periods import Calendario
from estalvia.engine.rules import Rule, RuleSet
from estalvia.ingestion.hourly import Ingesta

MADRID = ZoneInfo("Europe/Madrid")
FUENTE = "precio de la factura del cliente"


class FaltaDato(ValueError):
    """Falta un dato para calcular; el mensaje dice cuál. No se usa nunca un valor por defecto."""


@dataclass(frozen=True)
class PrecioContrato:
    """Precios pactados que imprime la factura (la IA los lee; el motor los usa)."""
    energia_eur_kwh: dict[str, Decimal]
    potencia_eur_kw_anio: dict[str, Decimal]

    def reglas(self, tarifa: str, desde) -> list[Rule]:
        reglas = [Rule(id=f"CONTRATO-ENE-{p}", kind="energia_eur_kwh", tariff=tarifa, period=p, value=v,
                       unit="EUR/kWh", valid_from=desde, source=FUENTE) for p, v in self.energia_eur_kwh.items()]
        return reglas + [Rule(id=f"CONTRATO-POT-{p}", kind="potencia_eur_kw_anio", tariff=tarifa, period=p,
                              value=v, unit="EUR/kW/año", valid_from=desde, source=FUENTE)
                         for p, v in self.potencia_eur_kw_anio.items()]


@dataclass(frozen=True)
class Comparacion:
    base: Desglose
    escenario: Desglose

    @property
    def ahorro(self) -> Decimal:
        return self.base.total - self.escenario.total


def _limites(periodo: Periodo) -> tuple[datetime, datetime]:
    return (datetime.combine(periodo.inicio, time(), MADRID),
            datetime.combine(periodo.fin + timedelta(days=1), time(), MADRID))


def consumo_por_periodo(site: SiteParams, ingesta: Ingesta, calendario: Calendario,
                        periodo: Periodo) -> dict[str, Decimal]:
    """kWh por periodo tarifario del periodo facturado. Falta alguna hora o hay consumo negativo: FaltaDato."""
    desde, hasta = _limites(periodo)
    utc = ZoneInfo("UTC")
    horas_esperadas = int((hasta.astimezone(utc) - desde.astimezone(utc)).total_seconds() // 3600)
    horas = sum(1 for x in ingesta.lecturas if desde <= x.instante_utc < hasta)
    if horas != horas_esperadas:
        raise FaltaDato(f"consumo incompleto en el periodo facturado: {horas} de {horas_esperadas} horas")
    if any(x.kwh < 0 for x in ingesta.lecturas if desde <= x.instante_utc < hasta):
        raise FaltaDato("consumo negativo en el periodo facturado")
    totales = ingesta.totales_por_periodo(calendario, tarifa=site.tarifa, desde=desde, hasta=hasta)
    return {p: t.kwh for p, t in totales.items()}


def desglose(site: SiteParams, kwh_por_periodo: dict[str, Decimal], reglas: RuleSet, precios: PrecioContrato,
             periodo: Periodo) -> Desglose:
    """Factura recalculada por el motor con estos kWh por periodo y los precios de la factura."""
    for p in sorted(kwh_por_periodo):
        if p not in precios.energia_eur_kwh:
            raise FaltaDato(f"falta el precio de energía del periodo {p}")
    for p in sorted(site.potencia_contratada_kw):
        if p not in precios.potencia_eur_kw_anio:
            raise FaltaDato(f"falta el precio de potencia del periodo {p}")
    todas = RuleSet(list(reglas.rules) + precios.reglas(site.tarifa, periodo.inicio))
    return calcular_factura(site, Lecturas(dict(kwh_por_periodo)), todas, periodo)


def linea_base(site: SiteParams, ingesta: Ingesta, calendario: Calendario, reglas: RuleSet,
               precios: PrecioContrato, periodo: Periodo) -> Desglose:
    return desglose(site, consumo_por_periodo(site, ingesta, calendario, periodo), reglas, precios, periodo)


def comparar(site: SiteParams, ingesta_base: Ingesta, ingesta_escenario: Ingesta, calendario: Calendario,
             reglas: RuleSet, precios: PrecioContrato, periodo: Periodo) -> Comparacion:
    return Comparacion(linea_base(site, ingesta_base, calendario, reglas, precios, periodo),
                       linea_base(site, ingesta_escenario, calendario, reglas, precios, periodo))
