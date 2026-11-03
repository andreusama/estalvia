"""Birròmetro: el cálculo del barril es exacto y cada usuario ve solo sus barriles. Datos inventados."""

from datetime import date
from decimal import Decimal as D

import pytest

from prototipos.bar import birrometro
from prototipos.bar.models import Barril
from prototipos.bar.tests.conftest import cliente_de, usuario

pytestmark = pytest.mark.django_db

DATOS = {
    "marca": "Marca de Prueba", "litros": "30", "fecha": "2026-10-01", "precio": "90,00", "precio_venta": "2.50",
    "servicio_cl": "20", "merma": "8", "iva_venta": "10",
}  # fmt: skip


def test_el_calculo_de_un_barril_es_exacto():
    # 30 L con un 8 % de merma = 27,6 L = 138 cañas de 20 cl; a 2,50 € con 10 % de IVA entran 313,64 € sin IVA
    r = birrometro.calcular(D("30"), D("90.00"), D("2.50"), 20, D("8"), D("10"))
    assert r.servicios == 138 and r.litros_perdidos == D("2.4")
    assert r.ingresos_netos == D("313.64") and r.beneficio == D("223.64") and r.margen == D("71.3")
    assert (r.coste_servicio, r.coste_litro) == (D("0.65"), D("3.00"))
    assert r.precio_minimo == D("0.72")  # 90 × 1,10 ÷ 138 = 0,7174 → se redondea hacia arriba
    assert r.gana


def test_a_un_precio_bajo_se_pierde_dinero():
    r = birrometro.calcular(D("30"), D("90.00"), D("0.50"), 20, D("8"), D("10"))
    assert r.beneficio < 0 and not r.gana and r.margen < 0


def test_a_su_precio_minimo_ya_no_se_pierde():
    r = birrometro.calcular(D("30"), D("90.00"), D("2.50"), 20, D("8"), D("10"))
    en_minimo = birrometro.calcular(D("30"), D("90.00"), r.precio_minimo, 20, D("8"), D("10"))
    assert en_minimo.beneficio >= 0


def test_una_racion_mas_grande_que_el_barril_no_da_division_por_cero():
    r = birrometro.calcular(D("1"), D("10.00"), D("2.50"), 50, D("40"), D("10"))  # 0,6 L → 1 ración de 50 cl
    assert r.servicios == 1
    r0 = birrometro.calcular(D("1"), D("10.00"), D("2.50"), 50, D("40"), D("21"))
    assert r0.servicios == 1 and birrometro.calcular(D("1"), D("1"), D("2"), 50, D("40"), D("10")).servicios == 1


def test_cambio_de_precio_respecto_al_anterior():
    assert birrometro.cambio_de_precio(D("3.30"), D("3.00")) == D("10.0")
    assert birrometro.cambio_de_precio(D("2.85"), D("3.00")) == D("-5.0")
    assert birrometro.cambio_de_precio(D("3.00"), None) is None


def test_la_pagina_calcula_con_los_datos_de_la_url(web):
    html = web.get("/bar/birrometro/", DATOS).content.decode()
    assert "Ganas" in html and "138" in html and "223,64" in html and "313,64" in html


def test_el_deslizador_pide_solo_el_resultado(web):
    r = web.get("/bar/birrometro/", {**DATOS, "precio_venta": "0.50"}, headers={"X-Requested-With": "fetch"})
    html = r.content.decode()
    assert "<html" not in html and "Pierdes dinero" in html and "Precio mínimo para no perder" in html


def test_datos_no_validos_se_explican_sin_calcular(web):
    html = web.get("/bar/birrometro/", {**DATOS, "litros": "0", "precio": ""}).content.decode()
    assert "entre 1 y 200 litros" in html and "Beneficio del barril" not in html


def test_guardar_un_barril_y_ver_la_subida_de_precio(web):
    assert web.post("/bar/birrometro/", DATOS).status_code == 302
    web.post("/bar/birrometro/", {**DATOS, "fecha": "2026-11-01", "precio": "99,00"})  # +10 % por litro
    assert Barril.objects.count() == 2
    html = web.get("/bar/birrometro/", {**DATOS, "fecha": "2026-11-01", "precio": "99,00"}).content.decode()
    assert "10,0 % de diferencia" in html and "pregunta a tu proveedor" in html
    assert "Tus barriles" in html and "Marca de Prueba" in html


def test_una_marca_con_otro_nombre_no_se_compara():
    ana = usuario("ana")
    viejo = Barril(
        propietario=ana, marca="Otra", litros=D("30"), fecha=date(2026, 9, 1), precio=D("90"), precio_venta=D("2.5")
    )
    assert birrometro.anterior_de_la_marca([viejo], "Marca de Prueba", date(2026, 10, 1)) is None
    assert birrometro.anterior_de_la_marca([viejo], " otra ", date(2026, 10, 1)) is viejo


def test_cada_usuario_ve_solo_sus_barriles():
    ana, beto = cliente_de("ana"), cliente_de("beto")
    ana.post("/bar/birrometro/", {**DATOS, "marca": "Secreta de Ana"})
    assert "Secreta de Ana" in ana.get("/bar/birrometro/").content.decode()
    assert "Secreta de Ana" not in beto.get("/bar/birrometro/").content.decode()
    # la subida de precio tampoco se calcula con barriles ajenos
    assert "diferencia" not in beto.get("/bar/birrometro/", {**DATOS, "marca": "Secreta de Ana"}).content.decode()


def test_sin_sesion_no_se_entra(client):
    assert client.get("/bar/birrometro/").status_code == 302


def test_el_resumen_enlaza_el_birrometro(web):
    assert "/bar/birrometro/" in web.get("/bar/").content.decode()
