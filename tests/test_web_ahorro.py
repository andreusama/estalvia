"""Pantalla de ahorro (spec #18, ticket #27) con un contrato y un consumo SINTÉTICOS.
Lunes laborable 2026-06-08, 1 kWh por hora: 8 kWh en cada uno de P1, P2 y P3 (2.0TD); precios 0,20 / 0,15 / 0,10;
potencia 4 kW en P1 y P2 a 30 y 3 EUR/kW/año. Línea base: total 5,03 (desglose a mano en test_analysis_habito).
Ahorro de mover 1 kWh (a mano): P1->P3 0,12 ; P1->P2 0,06 ; P2->P3 0,06 ; P2->P1 -0,08 ; P3->P2 -0,08 ; P3->P1 -0,14."""
import os
import re
import tempfile
from decimal import Decimal as D
from pathlib import Path

import django

CLAVE_WEB = "contrasena-de-prueba-no-real"
_TMP = Path(tempfile.mkdtemp())
CSV = _TMP / "consumo.csv"
CSV.write_text("date;hour;kwh\n" + "".join(f"2026-06-08;{h};1\n" for h in range(1, 25)), encoding="utf-8")
CONTRATO = _TMP / "contrato.yaml"
CONTRATO.write_text("""tarifa: 2.0TD
potencia_contratada_kw: {P1: "4", P2: "4"}
precios:
  energia_eur_kwh: {P1: "0.20", P2: "0.15", P3: "0.10"}
  potencia_eur_kw_anio: {P1: "30", P2: "3"}
periodo: {inicio: 2026-06-08, fin: 2026-06-08}
ie_uso: profesional
""", encoding="utf-8")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "estalvia.web.settings")
os.environ.setdefault("ESTALVIA_WEB_PASSWORD", CLAVE_WEB)
os.environ.setdefault("ESTALVIA_WEB_SECRET", "s" * 40)
django.setup()

from django.test import Client, override_settings  # noqa: E402

from estalvia.reports.figure_checker import cifras_inexistentes  # noqa: E402

CONFIG = dict(CONTRATO=str(CONTRATO), DATOS_CSV=str(CSV), DATOS_LECTOR="fecha_hora_kwh", WEB_PASSWORD=CLAVE_WEB)


def sesion():
    c = Client(HTTP_HOST="127.0.0.1")
    c.post("/login/", {"password": CLAVE_WEB})
    return c


def texto_de_resultados(html: str) -> str:
    seccion = re.search(r'<section id="resultados">(.*?)</section>', html, re.S).group(1)
    return re.sub(r"<[^>]+>", " ", seccion)


@override_settings(**CONFIG)
def test_la_pagina_exige_sesion():
    r = Client(HTTP_HOST="127.0.0.1").get("/ahorro/")
    assert r.status_code == 302 and r["Location"].startswith("/login/")


@override_settings(**CONFIG)
def test_muestra_la_linea_base_y_los_habitos_ordenados_por_ahorro_de_1_kwh():
    html = sesion().get("/ahorro/").content.decode()
    assert "5,03" in html
    orden = re.findall(r'data-habito="(P\d)-(P\d)"', html)
    assert orden == [("P1", "P3"), ("P1", "P2"), ("P2", "P3"), ("P2", "P1"), ("P3", "P2"), ("P3", "P1")]
    assert "0,12" in html and "-0,14" in html and "No conviene" in html


@override_settings(**CONFIG)
def test_un_habito_propio_muestra_sensibilidad_confianza_y_anual_orientativo():
    html = sesion().get("/ahorro/", {"origen": "P1", "destino": "P3", "kwh": "4"}).content.decode()
    for esperado in ["0,12", "0,25", "0,50", "182,50", "orientativo", "baja"]:
        assert esperado in html


@override_settings(**CONFIG)
def test_un_habito_imposible_o_mal_escrito_se_explica_sin_romper_la_pagina():
    c = sesion()
    assert "origen" in c.get("/ahorro/", {"origen": "P1", "destino": "P3", "kwh": "9"}).content.decode()
    assert c.get("/ahorro/", {"origen": "P1", "destino": "P3", "kwh": "abc"}).status_code == 200
    assert c.get("/ahorro/", {"origen": "P9", "destino": "P3", "kwh": "1"}).status_code == 200


@override_settings(**CONFIG)
def test_toda_cifra_de_los_resultados_sale_del_motor():
    html = sesion().get("/ahorro/", {"origen": "P1", "destino": "P3", "kwh": "4"}).content.decode()
    # Líneas de la línea base, a mano: potencia 0,33 y 0,03 ; energía 1,60 / 1,20 / 0,80 ; IE 0,20 ; IVA 0,87.
    motor = {D("0.33"), D("0.03"), D("1.60"), D("1.20"), D("0.80"), D("0.20"), D("0.87"), D("5.03"),
             D("4.91"), D("4.78"), D("4.53"), D("0.12"), D("0.25"), D("0.50"), D("182.50"), D("91.25"),
             D("43.80"), D("0.06"), D("-0.08"), D("0.08"), D("0.14"), D("-0.14"),
             D(1), D(2), D(3), D(4), D(25), D(50), D(100), D(0), D(8)}
    assert cifras_inexistentes(texto_de_resultados(html), motor) == []


@override_settings(**{**CONFIG, "CONTRATO": ""})
def test_sin_contrato_la_pagina_lo_dice_y_no_inventa_nada():
    html = sesion().get("/ahorro/").content.decode()
    assert "ESTALVIA_CONTRATO" in html and "€" not in html


@override_settings(**{**CONFIG, "DATOS_CSV": str(_TMP / "no-existe.csv")})
def test_sin_consumo_legible_la_pagina_lo_dice():
    assert "consumo" in sesion().get("/ahorro/").content.decode()
