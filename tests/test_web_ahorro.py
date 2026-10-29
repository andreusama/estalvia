"""Informe de /ahorro/ (spec #18, tickets #27 y #33) con un contrato y un consumo SINTÉTICOS.
Lunes laborable 2026-06-08, 1 kWh por hora: 8 kWh en cada uno de P1, P2 y P3 (2.0TD); precios 0,20 / 0,15 / 0,10;
potencia 4 kW en P1 y P2 a 30 y 3 EUR/kW/año. Cifras a mano en test_analysis_informe: total 5,03 ; potencia 0,36 ;
energía 3,60 ; impuestos 1,07 ; techo P1->P3 1,01 (368,65 al año) ; P2->P3 0,50 (182,50 al año)."""
import os
import re
import tempfile
from decimal import Decimal as D
from pathlib import Path

import django
import pytest

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
    seccion = re.search(r'<section id="resultados">(.*)</section>', html, re.S).group(1)
    seccion = re.sub(r"<script.*?</script>", " ", seccion, flags=re.S)
    return re.sub(r"<[^>]+>", " ", seccion)


@override_settings(**CONFIG)
def test_la_pagina_exige_sesion():
    r = Client(HTTP_HOST="127.0.0.1").get("/ahorro/")
    assert r.status_code == 302 and r["Location"].startswith("/login/")


@override_settings(**CONFIG)
def test_el_informe_responde_cuanto_gasto_en_que_y_como_pagar_menos_sin_pedir_nada():
    html = sesion().get("/ahorro/").content.decode()
    for bloque in ("gasto", "donde", "ahorrar"):
        assert f'<section id="{bloque}"' in html
    for pregunta in ("¿Cuánto gasto?", "¿En qué lo gasto?", "¿Cómo puedo pagar menos?"):
        assert pregunta in html
    assert "5,03" in html and "Potencia contratada" in html and "Energía consumida" in html
    assert "<form method=\"get\"" not in html and "Prueba tu hábito" not in html and "data-habito" not in html
    # solo hay un formulario: la subida de ficheros
    assert 'id="ficheros"' in html and "name=\"origen\"" not in html and "name=\"kwh\"" not in html


@override_settings(**CONFIG)
def test_el_mapa_de_calor_y_los_periodos_son_visibles_sin_scripts_en_linea():
    html = sesion().get("/ahorro/").content.decode()
    assert 'id="mapa-calor"' in html and "Lunes" in html and re.search(r'class="i9"', html)
    assert "Horas caras" in html and "10-14 h y 18-22 h" in html and "Horas baratas" in html
    assert "style=" not in html
    for etiqueta in re.findall(r"<script[^>]*>", html):
        assert 'src="/static/' in etiqueta or 'type="application/json"' in etiqueta


@override_settings(**CONFIG)
def test_los_hallazgos_dicen_techo_teorico_y_nunca_prometen():
    texto = texto_de_resultados(sesion().get("/ahorro/").content.decode())
    assert "1,01" in texto and "368,65" in texto and "0,50" in texto and "182,50" in texto
    assert "techo teórico" in texto and "baja" in texto
    assert "garantiz" in texto.lower()  # el aviso obligatorio dice que no están garantizadas
    assert "te ahorrarás" not in texto.lower() and "ahorrarás seguro" not in texto.lower()


@override_settings(**CONFIG)
def test_el_aviso_obligatorio_del_tdd_esta_en_el_informe():
    html = sesion().get("/ahorro/").content.decode()
    assert ("Este informe es informativo. Se basa en los datos facilitados por el cliente y en la normativa vigente "
            "en la fecha indicada. Las cifras de ahorro son estimaciones, no están garantizadas y dependen de que se "
            "mantengan las condiciones de consumo y de precios.") in html


@override_settings(**CONFIG)
def test_los_periodos_p1_p2_p3_solo_aparecen_como_detalle_explicado():
    html = sesion().get("/ahorro/").content.decode()
    principal = re.sub(r"<details.*?</details>", " ", html, flags=re.S)
    principal = re.sub(r"<script.*?</script>", " ", principal, flags=re.S)
    principal = re.sub(r"<[^>]+>", " ", principal)
    assert not re.search(r"\bP[1-6]\b", principal)
    assert "<details" in html and "P1, P2, P3" in html


@override_settings(**CONFIG)
def test_toda_cifra_del_informe_sale_del_motor():
    texto = texto_de_resultados(sesion().get("/ahorro/").content.decode())
    motor = {D("5.03"), D("0.36"), D("3.60"), D("1.07"), D("1.01"), D("368.65"), D("0.50"), D("182.50"),
             D("0.25"), D("0.12"), D("91.25"), D("43.80"), D("1.60"), D("1.20"), D("0.80"), D("8"),
             D("33.3"), D("7.2"), D("71.6"), D("21.3"), D("100"), D("25"), D("50"), D("365"), D("2026"),
             D("0.20"), D("0.15"), D("0.10"), D("0.2"), D("0.1"), D("0.15"), D("0.8"), D("1"), D("24"), D("4"),
             D("2"), D("6"), D("9"), D("10"), D("14"), D("18"), D("22"), D("11"), D("12"), D("13"), D("0"),
             D("3"), D("5"), D("7")} | {D(n) for n in range(0, 25)}
    assert cifras_inexistentes(texto, motor) == []


@override_settings(**CONFIG)
def test_los_parametros_del_formulario_antiguo_no_rompen_ni_cambian_nada():
    c = sesion()
    r = c.get("/ahorro/", {"origen": "P1", "destino": "P3", "kwh": "4"})
    quitar = lambda r: re.sub(rb'name="csrfmiddlewaretoken" value="[^"]+"', b"", r.content)  # noqa: E731
    assert r.status_code == 200 and quitar(r) == quitar(c.get("/ahorro/"))


@override_settings(**{**CONFIG, "CONTRATO": ""})
def test_sin_contrato_la_pagina_lo_dice_y_no_inventa_nada():
    html = sesion().get("/ahorro/").content.decode()
    assert "ESTALVIA_CONTRATO" in html and "€" not in html


@override_settings(**{**CONFIG, "DATOS_CSV": str(_TMP / "no-existe.csv")})
def test_sin_consumo_legible_la_pagina_lo_dice():
    assert "consumo" in sesion().get("/ahorro/").content.decode()


def _contrato_con(cambio: str):
    ruta = _TMP / "malo.yaml"
    ruta.write_text(CONTRATO.read_text(encoding="utf-8") + cambio, encoding="utf-8")
    return str(ruta)



@pytest.mark.parametrize("texto", [
    "tarifa: 9.9XX\n",
    'precios: {energia_eur_kwh: {P1: "NaN", P2: "0.1", P3: "0.1"}, potencia_eur_kw_anio: {P1: "30"}}\n',
    'potencia_contratada_kw: {P1: "1e999"}\n', "periodo: {inicio: 2026-06-08, fin: 9999-12-31}\n",
    "periodo: {inicio: 2026-06-08 10:00:00, fin: 2026-06-08}\n", "periodo: {inicio: 2026-06-09, fin: 2026-06-08}\n",
    'precios: {energia_eur_kwh: {P1: "-5", P2: "0.1", P3: "0.1"}, potencia_eur_kw_anio: {P1: "30"}}\n',
    "tarifa: 3.0TD\n"])
def test_un_contrato_malo_se_explica_con_200_y_nunca_da_500(texto):
    with override_settings(**{**CONFIG, "CONTRATO": _contrato_con(texto)}):
        r = sesion().get("/ahorro/")
    assert r.status_code == 200 and "aviso" in r.content.decode() and "Traceback" not in r.content.decode()
