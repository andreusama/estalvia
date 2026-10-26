"""Hábito «mover X kWh del periodo A al B» (spec #18, ticket #20).

El motor recalcula la factura con los kWh movidos; aquí solo se decide qué se mueve y cuánta confianza merece.
El ahorro se da al 25, 50 y 100 % de lo propuesto (presentación de sensibilidad, no un dato regulatorio).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from estalvia.analysis.nucleo import PrecioContrato, consumo_por_periodo, desglose, limites_del_periodo
from estalvia.engine.calc import Desglose, Periodo, SiteParams
from estalvia.engine.periods import Calendario
from estalvia.engine.rules import RuleSet
from estalvia.extraction.schema import PERIODOS_ENERGIA
from estalvia.ingestion.hourly import Ingesta

PORCENTAJES = (25, 50, 100)
CENT = Decimal("0.01")
Confianza = Literal["alta", "media", "baja"]


class HabitoImposible(ValueError):
    """El hábito no se puede dar en la realidad o no tiene sentido; el mensaje dice por qué."""


@dataclass(frozen=True)
class Habito:
    origen: str
    destino: str
    kwh: Decimal


@dataclass(frozen=True)
class EvaluacionHabito:
    habito: Habito
    base: Desglose
    escenarios: dict[int, Desglose]
    confianza: Confianza
    meses_completos: int
    dias_periodo_facturado: int

    @property
    def ahorro(self) -> dict[int, Decimal]:
        return {pct: self.base.total - e.total for pct, e in self.escenarios.items()}

    anual_es_orientativo = True  # siempre: es el ahorro de un periodo extrapolado; la interfaz debe decirlo

    @property
    def ahorro_anual_orientativo(self) -> dict[int, Decimal]:
        """Ahorro del periodo facturado extrapolado a 365 días. Solo orientativo: no mira otras estaciones."""
        return {pct: (a * 365 / self.dias_periodo_facturado).quantize(CENT, ROUND_HALF_UP)
                for pct, a in self.ahorro.items()}


def _confianza(ingesta: Ingesta, periodo: Periodo) -> tuple[Confianza, int]:
    completos = [m for m in ingesta.calidad.meses.values() if m.completo]
    if len(completos) < 12:
        return "baja", len(completos)
    desde, hasta = limites_del_periodo(periodo)
    real_en_el_periodo = all(x.tipo == "real" for x in ingesta.lecturas if desde <= x.instante_utc < hasta)
    todo_real = real_en_el_periodo and all(m.estimadas == 0 and m.desconocidas == 0 for m in completos)
    return ("alta" if todo_real else "media"), len(completos)


def _validar(habito: Habito, tarifa: str, consumo: dict[str, Decimal]) -> None:
    validos = PERIODOS_ENERGIA[tarifa]
    if habito.origen not in validos or habito.destino not in validos:
        raise HabitoImposible(f"periodo fuera de la tarifa {tarifa}: usar {', '.join(validos)}")
    if habito.origen == habito.destino:
        raise HabitoImposible("el origen y el destino son el mismo periodo")
    if not habito.kwh.is_finite() or habito.kwh <= 0:
        raise HabitoImposible("los kWh a mover deben ser positivos")
    if habito.kwh > consumo.get(habito.origen, Decimal(0)):
        raise HabitoImposible(f"no se puede mover más de lo consumido en el origen {habito.origen}")


def evaluar_habito(site: SiteParams, ingesta: Ingesta, calendario: Calendario, reglas: RuleSet,
                   precios: PrecioContrato, periodo: Periodo, habito: Habito) -> EvaluacionHabito:
    consumo = consumo_por_periodo(site, ingesta, calendario, periodo)
    _validar(habito, site.tarifa, consumo)
    escenarios = {}
    for pct in PORCENTAJES:
        movido = habito.kwh * pct / 100
        nuevo = dict(consumo)
        nuevo[habito.origen] = consumo[habito.origen] - movido
        nuevo[habito.destino] = consumo.get(habito.destino, Decimal(0)) + movido
        escenarios[pct] = desglose(site, nuevo, reglas, precios, periodo)
    confianza, meses = _confianza(ingesta, periodo)
    return EvaluacionHabito(habito, desglose(site, consumo, reglas, precios, periodo), escenarios, confianza,
                            meses, len(periodo.dias()))
