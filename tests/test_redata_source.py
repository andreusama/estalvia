"""REDataSource: analiza la respuesta JSON:API. Carga sintética con la forma de la respuesta real."""
import json
from datetime import datetime, timezone
from decimal import Decimal as D

import pytest

from estalvia.prices.redata import REDataSource
from estalvia.prices.store import SourceError

RESPUESTA = json.dumps({
    "data": {"type": "Precios mercado peninsular en tiempo real", "id": "mer13"},
    "included": [
        {"type": "PVPC", "id": "1001", "attributes": {"title": "PVPC", "values": [
            {"value": 128.71, "datetime": "2026-06-10T00:00:00.000+02:00"}]}},
        {"type": "Precio mercado spot", "id": "600", "attributes": {"title": "Precio mercado spot",
         "values": [
             {"value": 85.28, "percentage": 0.4, "datetime": "2026-06-10T00:00:00.000+02:00"},
             {"value": 60.2, "percentage": 1, "datetime": "2026-06-10T00:15:00.000+02:00"}]}},
    ],
})
DESDE = datetime(2026, 6, 9, 22, 0, tzinfo=timezone.utc)
HASTA = datetime(2026, 6, 10, 22, 0, tzinfo=timezone.utc)


def fuente(cuerpo):
    visto = {}

    def get(url, headers):
        visto["url"], visto["headers"] = url, headers
        return cuerpo

    return REDataSource(http_get=get), visto


def test_extrae_la_serie_spot_en_utc_con_decimales_exactos():
    f, visto = fuente(RESPUESTA)
    puntos = f.fetch(DESDE, HASTA)
    assert [p.instante_utc for p in puntos] == [
        datetime(2026, 6, 9, 22, 0, tzinfo=timezone.utc), datetime(2026, 6, 9, 22, 15, tzinfo=timezone.utc)]
    assert [p.eur_mwh for p in puntos] == [D("85.28"), D("60.2")]
    assert "precios-mercados-tiempo-real" in visto["url"]
    assert "start_date=2026-06-10T00:00" in visto["url"] and "end_date=2026-06-10T23:59" in visto["url"]
    assert visto["headers"]["Accept"].startswith("application/json")


def test_respuesta_sin_la_serie_spot_es_error():
    f, _ = fuente(json.dumps({"included": [{"id": "1001", "attributes": {"values": []}}]}))
    with pytest.raises(SourceError, match="spot"):
        f.fetch(DESDE, HASTA)


def test_json_invalido_o_error_http_es_error_de_fuente():
    f, _ = fuente("<html>")
    with pytest.raises(SourceError):
        f.fetch(DESDE, HASTA)

    def cae(url, headers):
        raise OSError("sin red")

    with pytest.raises(SourceError, match="sin red"):
        REDataSource(http_get=cae).fetch(DESDE, HASTA)


def test_http_4xx_es_error_permanente_y_5xx_no():
    import urllib.error

    def http(codigo):
        def get(url, headers):
            raise urllib.error.HTTPError(url, codigo, "x", {}, None)
        return get

    with pytest.raises(SourceError) as e400:
        REDataSource(http_get=http(400)).fetch(DESDE, HASTA)
    with pytest.raises(SourceError) as e503:
        REDataSource(http_get=http(503)).fetch(DESDE, HASTA)
    assert e400.value.permanente and not e503.value.permanente


def test_fecha_sin_zona_horaria_se_rechaza():
    f, _ = fuente(RESPUESTA)
    with pytest.raises(ValueError, match="zona horaria"):
        f.fetch(datetime(2026, 6, 10), HASTA)
