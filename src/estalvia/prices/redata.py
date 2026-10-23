"""Fuente de precios REData (Red Eléctrica). API pública sin autenticación, solo GET.

Docs: https://www.ree.es/en/datos/apidata. Widget `mercados/precios-mercados-tiempo-real`.
La serie spot (id 600) llega en resolución nativa (hoy cuartohoraria); NO se promedia aquí.
VERIFICAR: unidad (se asume EUR/MWh), zona horaria de start_date/end_date (se envía hora de
Madrid), límites de uso y condiciones de reutilización del API (citar www.ree.es y la fecha
de última actualización según las condiciones generales de reutilización de REE).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from estalvia.ingestion.hourly import MADRID

from .store import PricePoint, SourceError

BASE = "https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real"
SERIE_SPOT = "600"


def _http_get(url: str, headers: dict[str, str]) -> str:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:  # URL fija https
        return r.read().decode("utf-8")


class REDataSource:
    name = "redata"
    # REE pide citar la fuente y la fecha de última actualización (VERIFICAR las condiciones del API).
    atribucion = "Fuente: Red Eléctrica (www.ree.es), REData"

    def __init__(self, http_get: Callable[[str, dict[str, str]], str] = _http_get):
        self._get = http_get

    def fetch(self, desde: datetime, hasta: datetime) -> list[PricePoint]:
        if desde.tzinfo is None or hasta.tzinfo is None:
            raise ValueError("las fechas deben llevar zona horaria")
        inicio = desde.astimezone(MADRID)
        fin = (hasta - timedelta(minutes=1)).astimezone(MADRID)  # hasta es exclusivo
        url = f"{BASE}?start_date={inicio:%Y-%m-%dT%H:%M}&end_date={fin:%Y-%m-%dT%H:%M}&time_trunc=hour"
        try:
            cuerpo = self._get(url, {"Accept": "application/json", "Content-Type": "application/json"})
            datos = json.loads(cuerpo, parse_float=Decimal)
        except urllib.error.HTTPError as e:  # 4xx (salvo 429) no mejora al reintentar
            raise SourceError(f"REData: HTTP {e.code}", permanente=e.code < 500 and e.code != 429) from e
        except (OSError, ValueError) as e:
            raise SourceError(f"REData: {e}") from e
        serie = next((i for i in datos.get("included", []) if i.get("id") == SERIE_SPOT), None)
        if serie is None:
            raise SourceError("REData: la respuesta no contiene la serie de precio spot (id 600)")
        try:
            return [PricePoint(datetime.fromisoformat(v["datetime"]).astimezone(timezone.utc),
                               Decimal(str(v["value"])))
                    for v in serie["attributes"]["values"]]
        except (KeyError, ValueError, TypeError) as e:
            raise SourceError(f"REData: formato inesperado ({e})") from e
