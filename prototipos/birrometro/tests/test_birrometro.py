"""Birròmetro: el reparto del barril es exacto, no deja pasarse de litros y cada usuario ve solo lo suyo."""

from datetime import date
from decimal import Decimal as D

import pytest

from prototipos.birrometro import calculo as birrometro
from prototipos.birrometro.calculo import Racion
from prototipos.birrometro.models import Barril, RacionBarril
from prototipos.birrometro.tests.conftest import cliente_de, usuario

pytestmark = pytest.mark.django_db

# 30 L con un 8 % de merma = 27,6 L servibles. 20 jarras (8 L) + 60 cañas (12 L) + 40 zuritos (6 L) = 26 L
DATOS = {
    "marca": "Marca de Prueba", "litros": "30", "fecha": "2026-10-01", "precio": "90,00", "merma": "8",
    "iva_venta": "10",
    "zurito_cl": "15", "zurito_pvp": "1.80", "zurito_n": "40",
    "cana_cl": "20", "cana_pvp": "2.50", "cana_n": "60",
    "jarra_cl": "40", "jarra_pvp": "4.00", "jarra_n": "20",
}  # fmt: skip
RACIONES = [Racion("Zurito", 15, D("1.80"), 40), Racion("Caña", 20, D("2.50"), 60), Racion("Jarra", 40, D("4.00"), 20)]


def test_el_reparto_del_barril_es_exacto():
    r = birrometro.calcular(D("30"), D("90.00"), RACIONES, D("8"), D("10"))
    assert r.litros_utiles == D("27.6") and r.litros_servidos == D("26") and r.litros_sobran == D("1.6")
    # entra (40 × 1,80 + 60 × 2,50 + 20 × 4,00) = 302 con IVA → 274,55 sin IVA
    assert r.ingresos_netos == D("274.55") and r.beneficio == D("184.55") and r.margen == D("67.2")
    assert r.gana


def test_cada_racion_tiene_su_coste_y_lo_que_ganas():
    r = birrometro.calcular(D("30"), D("90.00"), RACIONES, D("8"), D("10"))
    zurito, cana, jarra = r.lineas
    # el barril cuesta 90 / 27,6 L = 3,2609 €/L útil
    assert (zurito.coste, cana.coste, jarra.coste) == (D("0.49"), D("0.65"), D("1.30"))
    assert (jarra.venta_neta, jarra.beneficio) == (D("3.64"), D("2.33"))
    assert (zurito.maximo, cana.maximo, jarra.maximo) == (184, 138, 69)
    assert jarra.precio_minimo == D("1.44")  # 1,3043 × 1,10 = 1,4348 → hacia arriba


def test_sin_sacar_nada_el_beneficio_es_la_perdida_del_barril():
    r = birrometro.calcular(D("30"), D("90.00"), [Racion("Caña", 20, D("2.50"), 0)], D("8"), D("10"))
    assert not r.sirve_algo and r.beneficio == D("-90.00") and r.margen is None


def test_el_litro_que_no_repartes_se_pierde():
    todo = birrometro.calcular(D("30"), D("90.00"), [Racion("Caña", 20, D("2.50"), 138)], D("8"), D("10"))
    la_mitad = birrometro.calcular(D("30"), D("90.00"), [Racion("Caña", 20, D("2.50"), 69)], D("8"), D("10"))
    assert la_mitad.beneficio < todo.beneficio and la_mitad.litros_sobran > todo.litros_sobran


def test_cambio_de_precio_respecto_al_anterior():
    assert birrometro.cambio_de_precio(D("3.30"), D("3.00")) == D("10.0")
    assert birrometro.cambio_de_precio(D("2.85"), D("3.00")) == D("-5.0")
    assert birrometro.cambio_de_precio(D("3.00"), None) is None


def test_la_pagina_calcula_con_los_datos_de_la_url(web):
    html = web.get("/birrometro/", DATOS).content.decode()
    assert "Ganas" in html and "184,55" in html and "274,55" in html
    for tipo in ("Zurito · 15 cl", "Caña · 20 cl", "Jarra · 40 cl"):
        assert tipo in html


def test_no_deja_repartir_mas_litros_de_los_que_hay(web):
    html = web.get("/birrometro/", {**DATOS, "jarra_n": "69"}).content.decode()  # 8 + 12 + 27,6 > 27,6
    assert "Te pasas" in html and "Beneficio del barril" not in html
    assert web.post("/birrometro/", {**DATOS, "jarra_n": "69"}).status_code == 200
    assert not Barril.objects.exists()


def test_sin_raciones_enseña_cuantas_cabrian(web):
    html = web.get("/birrometro/", {**DATOS, "zurito_n": "", "cana_n": "", "jarra_n": ""}).content.decode()
    assert "Quedan 27,6 L" in html and "como mucho 69" in html and "Beneficio del barril" not in html


def test_el_deslizador_pide_solo_el_resultado(web):
    r = web.get("/birrometro/", {**DATOS, "jarra_pvp": "0.50"}, headers={"X-Requested-With": "fetch"})
    html = r.content.decode()
    assert "<html" not in html and "Lo que sacas de cada ración" in html and "Jarra · 40 cl" in html


def test_datos_no_validos_se_explican_sin_calcular(web):
    html = web.get("/birrometro/", {**DATOS, "litros": "0", "precio": ""}).content.decode()
    assert "entre 1 y 200 litros" in html and "Beneficio del barril" not in html


def test_guardar_un_barril_guarda_lo_que_sacas_de_cada_racion(web):
    assert web.post("/birrometro/", DATOS).status_code == 302
    b = Barril.objects.get()
    assert [(r.nombre, r.cl, r.precio_venta, r.cantidad) for r in b.raciones.all()] == [
        ("Zurito", 15, D("1.80"), 40), ("Caña", 20, D("2.50"), 60), ("Jarra", 40, D("4.00"), 20)
    ]  # fmt: skip
    assert "184,55" in web.get("/birrometro/").content.decode()  # el historial recalcula el beneficio


def test_ver_la_subida_de_precio_entre_barriles(web):
    web.post("/birrometro/", DATOS)
    web.post("/birrometro/", {**DATOS, "fecha": "2026-11-01", "precio": "99,00"})  # +10 % por litro
    html = web.get("/birrometro/", {**DATOS, "fecha": "2026-11-01", "precio": "99,00"}).content.decode()
    assert "10,0 % de diferencia" in html and "pregunta a tu proveedor" in html
    assert "Tus barriles" in html and "Marca de Prueba" in html


def test_una_marca_con_otro_nombre_no_se_compara():
    viejo = Barril(propietario=usuario("ana"), marca="Otra", litros=D("30"), fecha=date(2026, 9, 1), precio=D("90"))
    assert birrometro.anterior_de_la_marca([viejo], "Marca de Prueba", date(2026, 10, 1)) is None
    assert birrometro.anterior_de_la_marca([viejo], " otra ", date(2026, 10, 1)) is viejo


def test_cada_usuario_ve_solo_sus_barriles():
    ana, beto = cliente_de("ana"), cliente_de("beto")
    ana.post("/birrometro/", {**DATOS, "marca": "Secreta de Ana"})
    assert "Secreta de Ana" in ana.get("/birrometro/").content.decode()
    assert "Secreta de Ana" not in beto.get("/birrometro/").content.decode()
    assert "diferencia" not in beto.get("/birrometro/", {**DATOS, "marca": "Secreta de Ana"}).content.decode()
    assert RacionBarril.objects.count() == 3


def test_sin_sesion_no_se_entra(client):
    assert client.get("/birrometro/").status_code == 302


def test_la_portada_lista_el_birrometro_como_herramienta_aparte(web):
    portada = web.get("/").content.decode()
    assert "/birrometro/" in portada and "/bar/" in portada
    assert "/birrometro/" not in web.get("/bar/").content.decode()  # el Bar no lo menciona: es otra herramienta
