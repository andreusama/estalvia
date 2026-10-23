"""Lectura de consumo horario en el formato interno normalizado (TDD sección 6.2).

Formato: CSV con cabecera `instante,kwh,kvarh,tipo`; `instante` es ISO 8601 con desfase UTC
explícito (así las horas repetidas del cambio de hora no son ambiguas).
Función pura sobre bytes: sin disco, sin red.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
TIPOS = ("real", "estimada")
COLUMNAS = ("instante", "kwh", "kvarh", "tipo")


class IngestError(ValueError):
    """El fichero no se puede leer sin suponer nada; el mensaje dice la línea."""


@dataclass(frozen=True)
class Lectura:
    instante_utc: datetime
    instante_local: datetime  # Europe/Madrid
    kwh: Decimal
    kvarh: Decimal
    tipo: Literal["real", "estimada"]


@dataclass(frozen=True)
class CalidadMes:
    reales: int
    estimadas: int
    faltantes: int  # horas esperadas del mes (hora local de Madrid) sin lectura
    completo: bool


@dataclass(frozen=True)
class Calidad:
    # Horas (UTC) sin lectura entre la primera y la última; nunca se rellenan.
    huecos: list[datetime]
    # Mes local -> recuento. Incluye los meses sin lecturas entre el primero y el último con datos.
    meses: dict[tuple[int, int], CalidadMes]


@dataclass(frozen=True)
class Ingesta:
    lecturas: list[Lectura]
    calidad: Calidad


def _horas_del_mes(anio: int, mes: int) -> int:
    ini = datetime(anio, mes, 1, tzinfo=MADRID).astimezone(timezone.utc)
    sig = datetime(anio + (mes == 12), mes % 12 + 1, 1, tzinfo=MADRID).astimezone(timezone.utc)
    return int((sig - ini).total_seconds() // 3600)


def _calidad(lecturas: list[Lectura]) -> Calidad:
    if not lecturas:
        return Calidad([], {})
    presentes = {x.instante_utc for x in lecturas}
    primero, ultimo = min(presentes), max(presentes)
    huecos, t = [], primero
    while t <= ultimo:
        if t not in presentes:
            huecos.append(t)
        t += timedelta(hours=1)
    reales: dict[tuple[int, int], int] = {}
    estimadas: dict[tuple[int, int], int] = {}
    for x in lecturas:
        clave = (x.instante_local.year, x.instante_local.month)
        destino = reales if x.tipo == "real" else estimadas
        destino[clave] = destino.get(clave, 0) + 1
    a, m = primero.astimezone(MADRID).year, primero.astimezone(MADRID).month
    fin = (ultimo.astimezone(MADRID).year, ultimo.astimezone(MADRID).month)
    meses: dict[tuple[int, int], CalidadMes] = {}
    while (a, m) <= fin:
        r, e = reales.get((a, m), 0), estimadas.get((a, m), 0)
        falta = _horas_del_mes(a, m) - r - e
        meses[(a, m)] = CalidadMes(r, e, falta, falta == 0)
        a, m = a + (m == 12), m % 12 + 1
    return Calidad(huecos, meses)


def _decimal(valor: str, linea: int, campo: str) -> Decimal:
    try:
        d = Decimal(valor.strip())
    except InvalidOperation:
        raise IngestError(f"línea {linea}: {campo} no es un número: {valor!r}") from None
    if not d.is_finite():
        raise IngestError(f"línea {linea}: {campo} debe ser un número finito")
    return d


def ingest_hourly(datos: bytes) -> Ingesta:
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
        if utc in vistos:
            raise IngestError(f"línea {n}: instante duplicado {texto}")
        vistos.add(utc)
        lecturas.append(Lectura(utc, utc.astimezone(MADRID), _decimal(fila["kwh"], n, "kwh"),
                                _decimal(fila["kvarh"], n, "kvarh"), tipo))
    return Ingesta(lecturas, _calidad(lecturas))
