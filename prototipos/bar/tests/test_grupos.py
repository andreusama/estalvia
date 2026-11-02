"""Estado de los grupos albarán-factura (sin tolerancia) y la pantalla principal con datos de ejemplo."""

from decimal import Decimal as D

from django.test import Client

from plataforma._pruebas import CLAVE
from prototipos.bar.grupos import DIFF, OK, WAIT, Documento, Grupo, contar, secciones


def g(albaran, factura):
    return Grupo(
        "P",
        Documento("Albarán", "A-1", D(albaran)),
        None if factura is None else Documento("Factura", "F-1", D(factura)),
    )


def test_coincide_solo_si_es_exacto():
    assert g("100.00", "100.00").estado == OK


def test_un_centimo_ya_es_diferencia():
    x = g("100.00", "100.01")
    assert x.estado == DIFF and x.diferencia == D("0.01")
    assert "0,01 € de más" in x.nota


def test_factura_de_menos():
    assert "6,00 € de menos" in g("324.40", "318.40").nota


def test_sin_factura_es_pendiente():
    assert g("220.15", None).estado == WAIT


def test_secciones_ordenadas_y_sin_vacias():
    s = secciones([g("1", "1"), g("1", "2"), g("1", None)])
    assert [x["estado"] for x in s] == [DIFF, WAIT, OK]
    assert [x["estado"] for x in secciones([g("1", "1")])] == [OK]
    assert contar([g("1", "1"), g("1", "2")]) == {OK: 1, DIFF: 1, WAIT: 0}


def test_pantalla_principal_formato_espanol_y_simbolos():
    c = Client(HTTP_HOST="localhost")
    c.post("/entrar/", {"password": CLAVE})
    html = c.get("/bar/").content.decode()
    assert "1.248,60&nbsp;€" in html and "318,40&nbsp;€" in html
    assert "≠" in html and "=" in html and "?" in html
    assert "Datos de ejemplo" in html
