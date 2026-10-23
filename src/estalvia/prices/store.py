"""Almacén de precios de mercado con fecha de captura (TDD sección 6.3).

Un análisis se puede reproducir pidiendo los precios `as_of` una fecha de captura. Si la fuente
falla, el resultado es incompleto: nunca se rellena con valores supuestos. La caché es en memoria;
la persistencia llega con la capa de datos.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

log = logging.getLogger(__name__)


class SourceError(Exception):
    """La fuente no pudo servir los precios. `permanente`: reintentar no sirve (p. ej. HTTP 4xx)."""

    def __init__(self, mensaje: str, permanente: bool = False):
        super().__init__(mensaje)
        self.permanente = permanente


@dataclass(frozen=True)
class PricePoint:
    instante_utc: datetime
    eur_mwh: Decimal  # unidad a VERIFICAR contra la documentación de la fuente


class PriceSource(Protocol):
    name: str

    def fetch(self, desde: datetime, hasta: datetime) -> list[PricePoint]: ...


@dataclass(frozen=True)
class PriceResult:
    puntos: list[PricePoint]
    completo: bool
    capturado_en: datetime | None
    fuente: str
    error: str | None = None
    paso: timedelta | None = None  # resolución de los puntos (REData: 15 min); no se promedia
    atribucion: str | None = None  # texto de cita exigido por la fuente


@dataclass(frozen=True)
class _Captura:
    desde: datetime
    hasta: datetime
    capturado_en: datetime
    puntos: list[PricePoint]
    paso: timedelta


class PriceStore:
    def __init__(self, source: PriceSource, clock: Callable[[], datetime] | None = None,
                 sleep: Callable[[float], None] = time.sleep, reintentos: int = 3,
                 espera_base: float = 1.0):
        self._source = source
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep
        self._reintentos = reintentos
        self._espera_base = espera_base
        self._capturas: list[_Captura] = []

    def get(self, desde: datetime, hasta: datetime, as_of: datetime | None = None,
            refresh: bool = False) -> PriceResult:
        """Precios en [desde, hasta). `as_of` reproduce una captura previa sin tocar la fuente."""
        for fecha in (desde, hasta, as_of):
            if fecha is not None and fecha.tzinfo is None:
                raise ValueError("las fechas deben llevar zona horaria")
        if as_of is not None:  # reproducir: nunca consulta la fuente
            previas = [c for c in self._cubren(desde, hasta) if c.capturado_en <= as_of]
            if not previas:
                return self._incompleto(f"sin captura anterior a {as_of.isoformat()}")
            return self._resultado(max(previas, key=lambda c: c.capturado_en), desde, hasta)
        if not refresh:
            cubren = self._cubren(desde, hasta)
            if cubren:
                return self._resultado(max(cubren, key=lambda c: c.capturado_en), desde, hasta)
        try:
            puntos = self._traer(desde, hasta)
        except SourceError as e:
            log.warning("fuente %s falló: %s", self._source.name, e)
            return self._incompleto(str(e))
        if not puntos:  # éxito sin datos: no es un precio
            return self._incompleto("la fuente respondió sin precios")
        paso, faltan = _cobertura(puntos, desde, hasta)
        if faltan:  # respuesta parcial: no se cachea ni se entrega
            return self._incompleto(f"la fuente no cubre el rango: faltan {faltan} puntos")
        captura = _Captura(desde, hasta, self._clock(), puntos, paso)
        self._capturas.append(captura)
        return self._resultado(captura, desde, hasta)

    def _traer(self, desde: datetime, hasta: datetime) -> list[PricePoint]:
        for intento in range(self._reintentos):
            try:
                return self._source.fetch(desde, hasta)
            except SourceError as e:
                log.info("fuente %s, intento %d/%d falló: %s", self._source.name, intento + 1,
                         self._reintentos, e)
                if e.permanente or intento == self._reintentos - 1:
                    raise
                self._sleep(self._espera_base * 2**intento)
        raise SourceError("sin intentos")  # reintentos <= 0

    def _cubren(self, desde: datetime, hasta: datetime) -> list[_Captura]:
        return [c for c in self._capturas if c.desde <= desde and hasta <= c.hasta]

    def _resultado(self, c: _Captura, desde: datetime, hasta: datetime) -> PriceResult:
        puntos = [p for p in c.puntos if desde <= p.instante_utc < hasta]
        return PriceResult(puntos, True, c.capturado_en, self._source.name, None, c.paso,
                           getattr(self._source, "atribucion", None))

    def _incompleto(self, error: str) -> PriceResult:
        return PriceResult([], False, None, self._source.name, error)


def _cobertura(puntos: list[PricePoint], desde: datetime, hasta: datetime) -> tuple[timedelta, int]:
    """Paso de la serie y número de puntos que faltan para cubrir [desde, hasta) sin huecos."""
    instantes = sorted({p.instante_utc for p in puntos})
    if not instantes:
        return hasta - desde, 1
    if len(instantes) > 1:
        paso = min(b - a for a, b in zip(instantes, instantes[1:]))
    else:
        paso = hasta - desde
    esperados = int((hasta - desde) / paso)
    presentes = sum(1 for k in range(esperados) if desde + k * paso in set(instantes))
    return paso, esperados - presentes
