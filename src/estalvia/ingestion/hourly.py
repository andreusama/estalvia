"""Lectura de consumo horario en el formato interno normalizado (TDD sección 6.2).

Formato: CSV con cabecera `instante,kwh,kvarh,tipo`; `instante` es ISO 8601 con desfase UTC
explícito (así las horas repetidas del cambio de hora no son ambiguas).
Función pura sobre bytes: sin disco, sin red.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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
    tipo: str


def _decimal(valor: str, linea: int, campo: str) -> Decimal:
    try:
        d = Decimal(valor.strip())
    except InvalidOperation:
        raise IngestError(f"línea {linea}: {campo} no es un número: {valor!r}") from None
    if not d.is_finite() or d < 0:
        raise IngestError(f"línea {linea}: {campo} debe ser un número finito no negativo")
    return d


def ingest_hourly(datos: bytes) -> list[Lectura]:
    lector = csv.DictReader(io.StringIO(datos.decode("utf-8-sig")))
    if tuple(lector.fieldnames or ()) != COLUMNAS:
        raise IngestError(f"cabecera esperada {','.join(COLUMNAS)}")
    lecturas: list[Lectura] = []
    vistos: set[datetime] = set()
    for n, fila in enumerate(lector, start=2):
        try:
            t = datetime.fromisoformat(fila["instante"].strip())
        except ValueError:
            raise IngestError(f"línea {n}: instante no es ISO 8601: {fila['instante']!r}") from None
        if t.tzinfo is None:
            raise IngestError(f"línea {n}: instante sin desfase UTC; no se supone zona horaria")
        tipo = fila["tipo"].strip()
        if tipo not in TIPOS:
            raise IngestError(f"línea {n}: tipo debe ser real o estimada, no {tipo!r}")
        utc = t.astimezone(timezone.utc)
        if utc in vistos:
            raise IngestError(f"línea {n}: instante duplicado {fila['instante'].strip()}")
        vistos.add(utc)
        lecturas.append(Lectura(utc, utc.astimezone(MADRID), _decimal(fila["kwh"], n, "kwh"),
                                _decimal(fila["kvarh"], n, "kvarh"), tipo))
    return lecturas
