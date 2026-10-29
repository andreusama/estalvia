"""Informe automático para el cliente (spec #18, ticket #33): qué gasta, en qué y cómo puede pagar menos.

Todo importe sale del motor (línea base y hábitos); aquí solo se agrupa, se ordena y se nombra en lenguaje llano.
El usuario no introduce nada. La IA no interviene.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from estalvia.analysis.habito import PORCENTAJES, Confianza, Habito, candidatos, evaluar_habito
from estalvia.analysis.nucleo import PrecioContrato, consumo_por_periodo, limites_del_periodo, linea_base
from estalvia.engine.calc import Periodo, SiteParams
from estalvia.engine.periods import Calendario
from estalvia.engine.rules import RuleSet
from estalvia.extraction.schema import PERIODOS_ENERGIA
from estalvia.ingestion.hourly import Ingesta

CENT = Decimal("0.01")
DECIMO = Decimal("0.1")

# Nombres llanos de los periodos tarifarios. P1-P3 siguen apareciendo como detalle, con su explicación.
NOMBRES_2_0TD = {"P1": ("cara", "Horas caras"), "P2": ("normal", "Horas normales"), "P3": ("barata", "Horas baratas")}

# Líneas del motor -> grupo del reparto (nombre, explicación). El orden es el de la pantalla.
GRUPOS = (
    ("Potencia contratada", "Lo pagas por tener la potencia disponible, consumas o no."),
    ("Energía consumida", "Lo que cuesta la electricidad que gastas, kWh a kWh."),
    ("Bono social", "Cargo fijo con el que se financia el bono social, que no depende de lo que consumes."),
    ("Alquiler del contador", "Lo que cuesta alquilar el equipo de medida, consumas o no."),
    ("Impuestos", "Impuesto especial sobre la electricidad e IVA, que se aplican sobre lo anterior."),
)


def _grupo(concepto: str) -> str:
    if concepto.startswith("potencia"):
        return "Potencia contratada"
    if concepto.startswith("energia"):
        return "Energía consumida"
    if concepto == "bono social":
        return "Bono social"
    if concepto == "alquiler equipos":
        return "Alquiler del contador"
    return "Impuestos"


@dataclass(frozen=True)
class Parte:
    nombre: str
    explicacion: str
    importe: Decimal
    porcentaje: Decimal


@dataclass(frozen=True)
class PeriodoTarifario:
    codigo: str  # P1, P2...
    nombre: str
    nivel: str  # cara | normal | barata
    horario: str  # laborables; fines de semana y festivos: ver la explicación
    kwh: Decimal
    porcentaje_consumo: Decimal
    precio_kwh: Decimal
    coste_energia: Decimal


DIAS_SEMANA = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
NIVELES_MAPA = 9  # intensidades 0 (sin datos) a 9 (la hora de más consumo)
TOP = 3
PERCENTIL_FONDO = 10


@dataclass(frozen=True)
class Celda:
    kwh: Decimal | None  # None: ese día de la semana no está en el periodo facturado
    intensidad: int


@dataclass(frozen=True)
class FilaMapa:
    dia: str
    celdas: tuple[Celda, ...]  # 24, una por hora local


@dataclass(frozen=True)
class TipoDia:
    dias: int
    kwh_por_dia: Decimal
    coste_energia: Decimal


@dataclass(frozen=True)
class Fondo:
    kwh_hora: Decimal  # consumo que se supera el 90 % de las horas
    kwh: Decimal
    coste_energia: Decimal
    porcentaje_consumo: Decimal


@dataclass(frozen=True)
class DiaCaro:
    dia: date
    kwh: Decimal
    coste_energia: Decimal


@dataclass(frozen=True)
class HoraCara:
    hora: int
    coste_energia: Decimal


@dataclass(frozen=True)
class Hallazgo:
    """Mover consumo de un periodo caro a uno más barato. El 100 % es un techo teórico, no una promesa."""
    origen: str
    destino: str
    origen_periodo: PeriodoTarifario
    destino_periodo: PeriodoTarifario
    kwh_origen: Decimal
    kwh_movidos: dict[int, Decimal]
    ahorro: dict[int, Decimal]
    ahorro_anual: dict[int, Decimal]  # orientativo: extrapola el periodo facturado a 365 días
    confianza: Confianza

    @property
    def escalera(self) -> tuple[tuple[int, Decimal, Decimal, Decimal], ...]:
        """(% del consumo del origen que se mueve, kWh movidos, ahorro del periodo, ahorro anual orientativo)."""
        return tuple((pct, self.kwh_movidos[pct], self.ahorro[pct], self.ahorro_anual[pct]) for pct in PORCENTAJES)


@dataclass(frozen=True)
class Informe:
    total: Decimal
    periodo: Periodo
    reparto: tuple[Parte, ...]
    periodos_tarifarios: tuple[PeriodoTarifario, ...]
    mapa: tuple[FilaMapa, ...]
    perfil_laborable: tuple[Decimal | None, ...]  # kWh medios por hora local de un día laborable
    perfil_finde: tuple[Decimal | None, ...]  # ídem, fines de semana y festivos
    laborables: TipoDia
    finde: TipoDia
    fondo: Fondo
    dias_caros: tuple[DiaCaro, ...]
    horas_caras: tuple[HoraCara, ...]
    hallazgos: tuple[Hallazgo, ...]


def _reparto(lineas, total: Decimal) -> tuple[Parte, ...]:
    importes = {nombre: Decimal(0) for nombre, _ in GRUPOS}
    for linea in lineas:
        importes[_grupo(linea.concepto)] += linea.importe
    return tuple(Parte(n, e, importes[n], (importes[n] / total * 100).quantize(DECIMO, ROUND_HALF_UP))
                 for n, e in GRUPOS if importes[n] != 0)


def _horario(calendario: Calendario, tarifa: str, periodo: Periodo, p: str) -> str:
    """Horas del periodo en un día laborable, leídas del calendario (nunca escritas aquí)."""
    if tarifa != "2.0TD":
        return ""
    dia = next((d for d in periodo.dias() if d.weekday() < 5 and calendario.periodo_energia_2_0td(d, 12) != "P3"),
               None)
    if dia is None:
        return ""
    tramos: list[tuple[int, int]] = []
    for hora in range(24):
        if calendario.periodo_energia_2_0td(dia, hora) != p:
            continue
        if tramos and tramos[-1][1] == hora:
            tramos[-1] = (tramos[-1][0], hora + 1)
        else:
            tramos.append((hora, hora + 1))
    textos = [f"{a}-{b} h" for a, b in tramos]
    return " y ".join([", ".join(textos[:-1]), textos[-1]]) if len(textos) > 1 else textos[0]


def _periodos_tarifarios(site: SiteParams, kwh: dict[str, Decimal], precios: PrecioContrato, calendario: Calendario,
             periodo: Periodo) -> tuple[PeriodoTarifario, ...]:
    total = sum(kwh.values(), Decimal(0)) or Decimal(1)
    periodos = []
    for p in PERIODOS_ENERGIA[site.tarifa]:  # también los que no se usan: 0 kWh
        nivel, nombre = NOMBRES_2_0TD.get(p, ("normal", f"Periodo {p}")) if site.tarifa == "2.0TD" \
            else ("normal", f"Periodo {p}")
        consumido, precio = kwh.get(p, Decimal(0)), precios.energia_eur_kwh[p]
        periodos.append(PeriodoTarifario(p, nombre, nivel, _horario(calendario, site.tarifa, periodo, p), consumido,
                              (consumido / total * 100).quantize(DECIMO, ROUND_HALF_UP), precio,
                              (consumido * precio).quantize(CENT, ROUND_HALF_UP)))
    return tuple(periodos)


class Hora(NamedTuple):
    dia: date
    hora: int
    kwh: Decimal
    precio: Decimal  # EUR/kWh del periodo tarifario de esa hora

    @property
    def coste(self) -> Decimal:
        return self.kwh * self.precio


def _horas_del_periodo(site: SiteParams, ingesta: Ingesta, calendario: Calendario, precios: PrecioContrato,
                       periodo: Periodo) -> list[Hora]:
    desde, hasta = limites_del_periodo(periodo)
    return [Hora(x.instante_local.date(), x.instante_local.hour, x.kwh, precios.energia_eur_kwh[p])
            for x, p in ingesta.etiquetadas(calendario, tarifa=site.tarifa) if desde <= x.instante_utc < hasta]


def _mapa(horas) -> tuple[FilaMapa, ...]:
    sumas, cuentas = defaultdict(Decimal), defaultdict(int)
    for h in horas:
        sumas[(h.dia.weekday(), h.hora)] += h.kwh
        cuentas[(h.dia.weekday(), h.hora)] += 1
    medias = {k: sumas[k] / cuentas[k] for k in sumas}
    maximo = max(medias.values(), default=Decimal(0))
    def celda(k):
        if k not in medias:
            return Celda(None, 0)
        return Celda(medias[k], int(medias[k] / maximo * NIVELES_MAPA) if maximo else 0)
    return tuple(FilaMapa(nombre, tuple(celda((i, h)) for h in range(24))) for i, nombre in enumerate(DIAS_SEMANA))


def _perfil(horas: list[Hora], calendario: Calendario, festivo: bool) -> tuple[Decimal | None, ...]:
    sumas, cuentas = defaultdict(Decimal), defaultdict(int)
    for h in horas:
        if (calendario.tipo_dia(h.dia) == "D") == festivo:
            sumas[h.hora] += h.kwh
            cuentas[h.hora] += 1
    return tuple(sumas[h] / cuentas[h] if cuentas[h] else None for h in range(24))


def _tipo_dia(horas, calendario: Calendario, festivo: bool) -> TipoDia:
    del_tipo = [h for h in horas if (calendario.tipo_dia(h.dia) == "D") == festivo]
    dias = len({h.dia for h in del_tipo})
    return TipoDia(dias, sum((h.kwh for h in del_tipo), Decimal(0)) / dias if dias else Decimal(0),
                   sum((h.coste for h in del_tipo), Decimal(0)).quantize(CENT, ROUND_HALF_UP))


def _fondo(horas: list[Hora]) -> Fondo:
    """Lo que se gasta aunque la actividad baje: el consumo de la hora que deja por debajo al 10 % de las horas."""
    ordenadas = sorted(h.kwh for h in horas)
    nivel = ordenadas[(len(ordenadas) + PERCENTIL_FONDO - 1) // PERCENTIL_FONDO - 1] if ordenadas else Decimal(0)
    kwh = sum((min(h.kwh, nivel) for h in horas), Decimal(0))
    coste = sum((min(h.kwh, nivel) * h.precio for h in horas), Decimal(0))
    total = sum((h.kwh for h in horas), Decimal(0))
    return Fondo(nivel, kwh, coste.quantize(CENT, ROUND_HALF_UP),
                 (kwh / total * 100).quantize(DECIMO, ROUND_HALF_UP) if total else Decimal(0))


def _dias_y_horas_caros(horas) -> tuple[tuple[DiaCaro, ...], tuple[HoraCara, ...]]:
    por_dia, por_hora = defaultdict(lambda: [Decimal(0), Decimal(0)]), defaultdict(Decimal)
    for h in horas:
        por_dia[h.dia][0] += h.kwh
        por_dia[h.dia][1] += h.coste
        por_hora[h.hora] += h.coste
    dias = sorted(por_dia.items(), key=lambda kv: (-kv[1][1], kv[0]))[:TOP]
    horas_caras = sorted(por_hora.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP]
    return (tuple(DiaCaro(d, k, c.quantize(CENT, ROUND_HALF_UP)) for d, (k, c) in dias),
            tuple(HoraCara(h, c.quantize(CENT, ROUND_HALF_UP)) for h, c in horas_caras))


def construir_informe(site: SiteParams, ingesta: Ingesta, calendario: Calendario, reglas: RuleSet,
                      precios: PrecioContrato, periodo: Periodo) -> Informe:
    base = linea_base(site, ingesta, calendario, reglas, precios, periodo)
    kwh = consumo_por_periodo(site, ingesta, calendario, periodo)
    horas = _horas_del_periodo(site, ingesta, calendario, precios, periodo)
    dias_caros, horas_caras = _dias_y_horas_caros(horas)
    periodos = _periodos_tarifarios(site, kwh, precios, calendario, periodo)
    return Informe(base.total, periodo, _reparto(base.lineas, base.total), periodos,
                   _mapa(horas), _perfil(horas, calendario, False), _perfil(horas, calendario, True),
                   _tipo_dia(horas, calendario, False), _tipo_dia(horas, calendario, True),
                   _fondo(horas), dias_caros, horas_caras,
                   _hallazgos(site, ingesta, calendario, reglas, precios, periodo, kwh, periodos))


def _hallazgos(site: SiteParams, ingesta: Ingesta, calendario: Calendario, reglas: RuleSet,
               precios: PrecioContrato, periodo: Periodo, kwh: dict[str, Decimal],
               periodos: tuple[PeriodoTarifario, ...]) -> tuple[Hallazgo, ...]:
    """Por cada periodo de origen, su mejor destino si ahorra algo. Se evalúa con todo lo consumido en el origen:
    nunca se mueve más de lo consumido (lo garantiza `evaluar_habito`)."""
    mejor = {}
    for c in candidatos(site, ingesta, calendario, reglas, precios, periodo):  # del que más ahorra al que menos
        if c.ahorro_por_kwh > 0:
            mejor.setdefault(c.origen, c)
    por_periodo = {f.codigo: f for f in periodos}
    hallazgos = []
    for origen, c in mejor.items():
        ev = evaluar_habito(site, ingesta, calendario, reglas, precios, periodo, Habito(origen, c.destino, kwh[origen]))
        if ev.ahorro[100] > 0:
            hallazgos.append(Hallazgo(origen, c.destino, por_periodo[origen], por_periodo[c.destino], kwh[origen],
                                      {pct: kwh[origen] * pct / 100 for pct in PORCENTAJES},
                                      ev.ahorro, ev.ahorro_anual_orientativo, ev.confianza))
    return tuple(sorted(hallazgos, key=lambda x: (-x.ahorro[100], x.origen)))
