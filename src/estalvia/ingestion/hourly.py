"""Lectura de consumo horario (TDD sección 6.2) con un lector aislado por formato.

Lectores:
- `interno` (por defecto): CSV con cabecera `instante,kwh,kvarh,tipo`; `instante` es ISO 8601 con desfase
  UTC explícito (así las horas repetidas del cambio de hora no son ambiguas).
- `fecha_hora_kwh`: export de un portal de comercializadora, cabecera `date;hour;kwh`, separador `;`,
  coma decimal, fecha local de Madrid y hora 1-24 donde la hora N es el intervalo que TERMINA en N
  (hora 1 = 00:00-01:00). No trae kVArh ni marca real/estimada: quedan desconocidos, no se suponen.

Función pura sobre bytes: sin disco, sin red.
"""
from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

from estalvia.engine.periods import Calendario

MADRID = ZoneInfo("Europe/Madrid")
TIPOS = ("real", "estimada")
COLUMNAS = ("instante", "kwh", "kvarh", "tipo")
COLUMNAS_FECHA_HORA_KWH = ("date", "hour", "kwh")
TARIFAS_6_PERIODOS = ("3.0TD", "6.1TD", "6.2TD", "6.3TD", "6.4TD")


class IngestError(ValueError):
    """El fichero no se puede leer sin suponer nada; el mensaje dice la línea."""


@dataclass(frozen=True)
class Lectura:
    instante_utc: datetime
    instante_local: datetime  # Europe/Madrid
    kwh: Decimal
    kvarh: Decimal | None  # None: el formato de origen no lo trae
    tipo: Literal["real", "estimada", "desconocida"]


@dataclass(frozen=True)
class CalidadMes:
    reales: int
    estimadas: int
    faltantes: int  # horas esperadas del mes (hora local de Madrid) sin lectura
    completo: bool
    desconocidas: int = 0  # lecturas cuyo formato de origen no distingue real de estimada


@dataclass(frozen=True)
class Calidad:
    # Horas (UTC) sin lectura ENTRE la primera y la última lectura; nunca se rellenan. Las horas que
    # faltan antes de la primera o después de la última no se listan, pero sí cuentan en `faltantes` del mes.
    huecos: list[datetime]
    # Mes local -> recuento. Incluye los meses sin lecturas entre el primero y el último con datos.
    meses: dict[tuple[int, int], CalidadMes]


@dataclass(frozen=True)
class TotalPeriodo:
    kwh: Decimal
    kvarh: Decimal | None  # None si alguna lectura del periodo no trae kVArh


@dataclass(frozen=True)
class Ingesta:
    lecturas: list[Lectura]
    calidad: Calidad

    def etiquetadas(self, calendario: Calendario, tarifa: str = "3.0TD") -> list[tuple[Lectura, str]]:
        """Cada lectura con su periodo de energía (solo península). 3.0TD y 6.xTD: P1-P6; 2.0TD: P1-P3."""
        return _etiquetar(self.lecturas, calendario, tarifa)

    def totales_por_periodo(self, calendario: Calendario, desde: datetime | None = None,
                            hasta: datetime | None = None, tarifa: str = "3.0TD") -> dict[str, TotalPeriodo]:
        """kWh y kVArh por periodo en [desde, hasta); sin límites, todas las lecturas."""
        for limite in (desde, hasta):
            if limite is not None and limite.tzinfo is None:
                raise ValueError("el rango debe llevar zona horaria")
        if desde is not None and hasta is not None and desde >= hasta:
            raise ValueError("el rango es vacío o inverso: desde debe ser anterior a hasta")
        inicio = desde or datetime.min.replace(tzinfo=timezone.utc)
        fin = hasta or datetime.max.replace(tzinfo=timezone.utc)
        en_rango = [lectura for lectura in self.lecturas if inicio <= lectura.instante_utc < fin]
        totales: dict[str, TotalPeriodo] = {}
        for lectura, periodo in _etiquetar(en_rango, calendario, tarifa):
            acumulado = totales.get(periodo, TotalPeriodo(Decimal(0), Decimal(0)))
            kvarh = None if acumulado.kvarh is None or lectura.kvarh is None else acumulado.kvarh + lectura.kvarh
            totales[periodo] = TotalPeriodo(acumulado.kwh + lectura.kwh, kvarh)
        return totales


def _etiquetar(lecturas: list[Lectura], calendario: Calendario, tarifa: str) -> list[tuple[Lectura, str]]:
    if tarifa == "2.0TD":
        periodo = calendario.periodo_energia_2_0td
    elif tarifa in TARIFAS_6_PERIODOS:
        periodo = calendario.periodo
    else:
        raise ValueError(f"tarifa no soportada para etiquetar periodos: {tarifa!r}")
    return [(x, periodo(x.instante_local.date(), x.instante_local.hour)) for x in lecturas]


def _mes_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return anio + (mes == 12), mes % 12 + 1


def _horas_del_mes(anio: int, mes: int) -> int:
    inicio = datetime(anio, mes, 1, tzinfo=MADRID).astimezone(timezone.utc)
    siguiente = datetime(*_mes_siguiente(anio, mes), 1, tzinfo=MADRID).astimezone(timezone.utc)
    return int((siguiente - inicio).total_seconds() // 3600)


def _calidad(lecturas: list[Lectura]) -> Calidad:
    if not lecturas:
        return Calidad([], {})
    presentes = {x.instante_utc for x in lecturas}
    primero, ultimo = min(presentes), max(presentes)
    huecos, instante = [], primero
    while instante <= ultimo:
        if instante not in presentes:
            huecos.append(instante)
        instante += timedelta(hours=1)
    cuenta = Counter(((x.instante_local.year, x.instante_local.month), x.tipo) for x in lecturas)
    local_primero, local_ultimo = primero.astimezone(MADRID), ultimo.astimezone(MADRID)
    mes = (local_primero.year, local_primero.month)
    ultimo_mes = (local_ultimo.year, local_ultimo.month)
    meses: dict[tuple[int, int], CalidadMes] = {}
    while mes <= ultimo_mes:
        n_reales, n_estimadas = cuenta[(mes, "real")], cuenta[(mes, "estimada")]
        n_desconocidas = cuenta[(mes, "desconocida")]
        faltantes = _horas_del_mes(*mes) - n_reales - n_estimadas - n_desconocidas
        meses[mes] = CalidadMes(n_reales, n_estimadas, faltantes, faltantes == 0, n_desconocidas)
        mes = _mes_siguiente(*mes)
    return Calidad(huecos, meses)


def _decimal(valor: str, linea: int, campo: str) -> Decimal:
    try:
        d = Decimal(valor.strip())
    except InvalidOperation:
        raise IngestError(f"línea {linea}: {campo} no es un número: {valor!r}") from None
    if not d.is_finite():
        raise IngestError(f"línea {linea}: {campo} debe ser un número finito")
    return d


def _leer_interno(datos: bytes) -> list[Lectura]:
    lector = csv.DictReader(io.StringIO(datos.decode("utf-8-sig")))
    if tuple(lector.fieldnames or ()) != COLUMNAS:
        raise IngestError(f"cabecera esperada {','.join(COLUMNAS)}")
    lecturas: list[Lectura] = []
    vistos: set[datetime] = set()
    for n, fila in enumerate(lector, start=2):
        texto = fila["instante"].strip()
        try:
            t = datetime.fromisoformat(texto)
        except ValueError:
            raise IngestError(f"línea {n}: instante no es ISO 8601: {texto!r}") from None
        if t.tzinfo is None:
            raise IngestError(f"línea {n}: instante sin desfase UTC; no se supone zona horaria")
        tipo = fila["tipo"].strip()
        if tipo not in TIPOS:
            raise IngestError(f"línea {n}: tipo debe ser real o estimada, no {tipo!r}")
        utc = t.astimezone(timezone.utc)
        if utc.minute or utc.second or utc.microsecond:
            raise IngestError(f"línea {n}: el instante debe ser una hora en punto: {texto}")
        if utc in vistos:
            raise IngestError(f"línea {n}: instante duplicado {texto}")
        vistos.add(utc)
        lecturas.append(Lectura(utc, utc.astimezone(MADRID), _decimal(fila["kwh"], n, "kwh"),
                                _decimal(fila["kvarh"], n, "kvarh"), tipo))
    return lecturas


def _medianoche_utc(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, tzinfo=MADRID).astimezone(timezone.utc)


def _leer_fecha_hora_kwh(datos: bytes) -> list[Lectura]:
    lector = csv.DictReader(io.StringIO(datos.decode("utf-8-sig")), delimiter=";")
    if tuple(lector.fieldnames or ()) != COLUMNAS_FECHA_HORA_KWH:
        raise IngestError(f"cabecera esperada {';'.join(COLUMNAS_FECHA_HORA_KWH)}")
    lecturas: list[Lectura] = []
    vistos: set[datetime] = set()
    for n, fila in enumerate(lector, start=2):
        try:
            dia = date.fromisoformat(fila["date"].strip())
        except ValueError:
            raise IngestError(f"línea {n}: date no es AAAA-MM-DD: {fila['date']!r}") from None
        try:
            hora = int(fila["hour"].strip())
        except ValueError:
            raise IngestError(f"línea {n}: hora no es un entero: {fila['hour']!r}") from None
        # Horas reales del día local (23, 24 o 25). NO verificado con un fichero real de cambio de hora
        # de este portal: una hora fuera del día es error y una hora ausente sale como hueco en la calidad.
        horas_del_dia = int((_medianoche_utc(dia + timedelta(days=1)) - _medianoche_utc(dia)).total_seconds() // 3600)
        if not 1 <= hora <= horas_del_dia:
            raise IngestError(f"línea {n}: hora {hora} fuera del día {dia} (tiene {horas_del_dia} horas)")
        valor = fila["kwh"].strip()
        if "." in valor:
            raise IngestError(f"línea {n}: kwh debe usar coma decimal, no punto: {valor!r}")
        utc = _medianoche_utc(dia) + timedelta(hours=hora - 1)  # hora N = intervalo que termina en N
        if utc in vistos:
            raise IngestError(f"línea {n}: instante duplicado {dia} hora {hora}")
        vistos.add(utc)
        lecturas.append(Lectura(utc, utc.astimezone(MADRID), _decimal(valor.replace(",", "."), n, "kwh"),
                                None, "desconocida"))
    return lecturas


LECTORES: dict[str, Callable[[bytes], list[Lectura]]] = {
    "interno": _leer_interno,
    "fecha_hora_kwh": _leer_fecha_hora_kwh,
}


def ingest_hourly(datos: bytes, lector: str = "interno") -> Ingesta:
    if lector not in LECTORES:
        raise IngestError(f"lector desconocido: {lector!r} (disponibles: {', '.join(LECTORES)})")
    lecturas = LECTORES[lector](datos)
    return Ingesta(lecturas, _calidad(lecturas))
