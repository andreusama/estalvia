"""Comprobaciones deterministas: sin tolerancia, un céntimo ya es un fallo."""

from decimal import Decimal as D

import pytest

from prototipos.bar.comprobaciones import comprobar
from prototipos.bar.models import DesgloseIva, Documento, Linea
from prototipos.bar.numeros import a_decimal, eur, normalizar_referencia

pytestmark = pytest.mark.django_db


def doc(base="10.49", total="12.69", importe="10.49", cuota="2.20", cantidad="1", precio="10.49", descuento=None):
    d = Documento.objects.create(
        archivo=b"x",
        nombre_archivo="a.png",
        tipo_mime="image/png",
        sha256="h",
        numero="F-1",
        fecha="2026-10-21",
        proveedor_nombre="P",
        base_imponible=D(base),
        total=D(total),
    )
    Linea.objects.create(
        documento=d, cantidad=D(cantidad), precio_unitario=D(precio), importe=D(importe), descuento=descuento
    )
    DesgloseIva.objects.create(documento=d, tipo=D("21"), base=D(base), cuota=D(cuota))
    return d


def test_todo_cuadra():
    assert comprobar(doc()) == []


def test_un_centimo_de_diferencia_en_el_total_es_fallo():
    fallos = comprobar(doc(total="12.70"))
    assert [f.campo for f in fallos] == ["total"]
    assert "12,69" in fallos[0].texto and "12,70" in fallos[0].texto


def test_lineas_que_no_suman_la_base():
    fallos = comprobar(doc(base="10.50", total="12.70", cuota="2.20"))
    assert any(f.campo == "base_imponible" for f in fallos)


def test_iva_distinto_del_esperado():
    assert any("sería" in f.texto for f in comprobar(doc(cuota="2.21", total="12.70")))


def test_cantidad_por_precio_no_es_el_importe_salvo_con_descuento():
    assert any(f.campo == "lineas" for f in comprobar(doc(cantidad="2", precio="10.49", importe="10.49")))
    assert not any(
        f.campo == "lineas" for f in comprobar(doc(cantidad="2", precio="10.49", importe="10.49", descuento=D("50")))
    )


def test_faltan_datos_basicos():
    d = Documento.objects.create(archivo=b"x", nombre_archivo="a.png", tipo_mime="image/png", sha256="h2")
    assert {f.campo for f in comprobar(d)} == {"numero", "fecha", "proveedor_nombre"}


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("10.49", D("10.49")),
        ("10,49", D("10.49")),
        ("1.248,60", D("1248.60")),
        ("1,248.60", D("1248.60")),
        ("12,69 €", D("12.69")),
        ("", None),
        ("abc", None),
    ],
)
def test_leer_importes(texto, esperado):
    assert a_decimal(texto) == esperado


def test_formato_espanol_con_punto_de_miles():
    assert eur(D("1248.6")) == "1.248,60 €"


def test_referencias_con_formatos_distintos_son_la_misma():
    assert normalizar_referencia("A.28541") == normalizar_referencia("a-28541") == normalizar_referencia("A 28541")
