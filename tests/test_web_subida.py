"""Subida de CSV y PDF en la web local (ticket #32). Solo datos sintéticos y una IA falsa."""
import json
import os
import shutil
import stat
import subprocess
from decimal import Decimal as D
from pathlib import Path

import django
import pytest
from test_pdf_text import pdf_minimo

CLAVE_WEB = "contrasena-de-prueba-no-real"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "estalvia.web.settings")
os.environ.setdefault("ESTALVIA_WEB_PASSWORD", CLAVE_WEB)
os.environ.setdefault("ESTALVIA_WEB_SECRET", "s" * 40)
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client, override_settings  # noqa: E402

from estalvia.ai.gateway import ErrorIA, RespuestaIA  # noqa: E402
from estalvia.extraction.schema import FacturaExtraida  # noqa: E402
from estalvia.web.contrato import ErrorContrato  # noqa: E402
from estalvia.web.subida import contrato_desde_factura  # noqa: E402

RAIZ = Path(__file__).parents[1]
PDF_DE_LUZ = pdf_minimo([(50, 780, "Energia P1 8 kWh"), (50, 760, "Potencia P1 4 kW")])


def datos_factura(**cambios):
    base = {
        "comercializadora": "X", "cups": "[CUPS:abc]", "tarifa_acceso": "2.0TD", "modalidad_precio": "fijo",
        "periodo_facturado": {"inicio": "2026-06-01", "fin": "2026-06-30"},
        "potencia_contratada_kw": {"P1": "4", "P2": "4"},
        "energia_kwh": {"P1": "10", "P2": "10", "P3": "10"},
        "conceptos": [
            {"nombre": "Potencia P1", "cantidad": "4", "precio": "0.073", "importe": "8.76"},
            {"nombre": "Potencia P2", "cantidad": "4", "precio": "0.0082", "importe": "0.98"},
            {"nombre": "Energía P1", "cantidad": "10", "precio": "0.20", "importe": "2.00"},
            {"nombre": "Energía P2", "cantidad": "10", "precio": "0.15", "importe": "1.50"},
            {"nombre": "Energía P3", "cantidad": "10", "precio": "0.10", "importe": "1.00"},
            {"nombre": "Alquiler de equipos", "importe": "0.80"},
        ],
        "impuestos": {"electrico": "0.80", "iva": "3.00"}, "total": "18.84",
    }
    base.update(cambios)
    return FacturaExtraida.model_validate(base)


def test_el_contrato_sale_de_las_lineas_de_la_factura_por_nombre_y_periodo():
    c = contrato_desde_factura(datos_factura())
    assert c.precios.energia_eur_kwh == {"P1": D("0.20"), "P2": D("0.15"), "P3": D("0.10")}
    assert c.precios.potencia_eur_kw_anio == {"P1": D("0.073") * 365, "P2": D("0.0082") * 365}
    assert c.site.tarifa == "2.0TD" and c.site.potencia_contratada_kw == {"P1": D(4), "P2": D(4)}
    assert c.site.alquiler_importe == D("0.80") and c.site.aplica_bono_social is False
    assert (c.periodo.inicio.isoformat(), c.periodo.fin.isoformat()) == ("2026-06-01", "2026-06-30")


def test_facturas_en_catalan_terme_fix_terme_d_energia_lloguer_y_bo_social():
    conceptos = [
        {"nombre": "Terme fix P1", "cantidad": "4", "precio": "0.073", "importe": "8.76"},
        {"nombre": "Terme fix P2", "cantidad": "4", "precio": "0.0082", "importe": "0.98"},
        {"nombre": "Terme d'energia P1", "cantidad": "10", "precio": "0.20", "importe": "2.00"},
        {"nombre": "Terme d'energia P2", "cantidad": "10", "precio": "0.15", "importe": "1.50"},
        {"nombre": "Terme d'energia P3", "cantidad": "10", "precio": "0.10", "importe": "1.00"},
        {"nombre": "Finançament Bo Social (01SEP-02OCT)", "cantidad": "32", "precio": "0.02", "importe": "0.64"},
        {"nombre": "Lloguer", "importe": "0.85"},
    ]
    c = contrato_desde_factura(datos_factura(conceptos=conceptos))
    assert c.precios.potencia_eur_kw_anio == {"P1": D("0.073") * 365, "P2": D("0.0082") * 365}
    assert c.precios.energia_eur_kwh["P3"] == D("0.10") and c.site.alquiler_importe == D("0.85")
    assert c.site.aplica_bono_social is True


def test_si_falta_un_precio_no_se_estima_y_el_error_dice_cual():
    sin_p2 = [x for x in datos_factura().conceptos if x.nombre != "Energía P2"]
    with pytest.raises(ErrorContrato, match="energía P2"):
        contrato_desde_factura(datos_factura().model_copy(update={"conceptos": sin_p2}))


# --- POST /subir/ ---------------------------------------------------------------------------------------------
# Día sintético lunes 2026-06-08, 1 kWh por hora (8 kWh en cada periodo). Importes a mano, con redondeo a 2 decimales:
# energía 1,60 + 1,20 + 0,80; potencia 4 kW x 0,073 = 0,292 -> 0,29 y 4 kW x 0,0082 = 0,0328 -> 0,03; subtotal 3,92;
# IE 5,11269632 % de 3,92 = 0,2004 -> 0,20; IVA 21 % de 4,12 = 0,8652 -> 0,87; total 4,99.
CSV_BUENO = "date;hour;kwh\n" + "".join(f"2026-06-08;{h};1\n" for h in range(1, 25))
CSV_DOBLE = "date;hour;kwh\n" + "".join(f"2026-06-08;{h};2\n" for h in range(1, 25))
FACTURA_IA = {
    "comercializadora": "X", "cups": "[CUPS:abc123]", "tarifa_acceso": "2.0TD", "modalidad_precio": "fijo",
    "periodo_facturado": {"inicio": "2026-06-08", "fin": "2026-06-08"},
    "potencia_contratada_kw": {"P1": "4", "P2": "4"}, "energia_kwh": {"P1": "8", "P2": "8", "P3": "8"},
    "conceptos": [
        {"nombre": "Energía P1", "cantidad": "8", "precio": "0.20", "importe": "1.60"},
        {"nombre": "Energía P2", "cantidad": "8", "precio": "0.15", "importe": "1.20"},
        {"nombre": "Energía P3", "cantidad": "8", "precio": "0.10", "importe": "0.80"},
        {"nombre": "Potencia P1", "cantidad": "4", "precio": "0.073", "importe": "0.29"},
        {"nombre": "Potencia P2", "cantidad": "4", "precio": "0.0082", "importe": "0.03"},
    ],
    "impuestos": {"electrico": "0.20", "iva": "0.87"}, "total": "4.99",
}


class IAFalsa:
    def __init__(self, datos=None, error=None):
        self.datos, self.error, self.peticiones = datos if datos is not None else FACTURA_IA, error, []

    def completar(self, peticion):
        self.peticiones.append(peticion)
        if self.error:
            raise self.error
        return RespuestaIA("fin", json.dumps(self.datos), 100, 50)


@pytest.fixture
def web(tmp_path):
    ia = IAFalsa()
    with override_settings(UPLOADS_DIR=str(tmp_path / "uploads"), CACHE_DIR=str(tmp_path / "cache"),
                           DATOS_CSV="", CONTRATO="", WEB_PASSWORD=CLAVE_WEB,
                           DATOS_LECTOR="fecha_hora_kwh", FABRICA_IA=lambda: ia, MASK_KEY="m" * 32):
        c = Client(HTTP_HOST="127.0.0.1")
        c.post("/login/", {"password": CLAVE_WEB})
        c.uploads, c.ia = tmp_path / "uploads", ia
        yield c


def subir(c, nombre, contenido, **kw):
    if isinstance(contenido, str):
        contenido = contenido.encode()
    return c.post("/subir/", {"fichero": SimpleUploadedFile(nombre, contenido)}, **kw)


def test_subir_exige_sesion_y_csrf(tmp_path):
    with override_settings(UPLOADS_DIR=str(tmp_path), WEB_PASSWORD=CLAVE_WEB):
        r = subir(Client(HTTP_HOST="127.0.0.1"), "a.csv", CSV_BUENO)
        assert r.status_code == 302 and r["Location"].startswith("/login/") and not list(tmp_path.iterdir())
        c = Client(HTTP_HOST="127.0.0.1", enforce_csrf_checks=True)
        c.post("/login/", {"password": CLAVE_WEB}, HTTP_X_CSRFTOKEN="x")
        assert subir(c, "a.csv", CSV_BUENO).status_code == 403


def test_un_csv_valido_se_guarda_en_local_con_permisos_600_y_alimenta_la_curva(web):
    r = subir(web, "mi consumo (1).csv", CSV_BUENO)
    assert r.status_code == 200 and r.json()["ok"] is True
    guardado = web.uploads / "consumo.csv"
    assert guardado.read_text() == CSV_BUENO and stat.S_IMODE(guardado.stat().st_mode) == 0o600
    assert [p.name for p in web.uploads.iterdir()] == ["consumo.csv"]  # el nombre original no se usa
    assert "datos-curva" in web.get("/").content.decode()


def test_un_csv_mal_formado_se_rechaza_con_un_aviso_y_no_se_guarda(web):
    r = subir(web, "x.csv", "a,b\n1,2\n")
    assert r.status_code == 400 and "CSV" in r.json()["mensaje"]
    assert not (web.uploads / "consumo.csv").exists()


def test_tipo_nombre_y_tamano_incorrectos_se_rechazan(web):
    assert subir(web, "notas.txt", "hola").status_code == 400
    assert subir(web, "x.csv", b"%PDF-1.4 no soy csv").status_code == 400
    assert subir(web, "x.csv", CSV_BUENO + "#" * (2 * 1024 * 1024)).status_code == 413
    assert subir(web, "f.pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024)).status_code == 413
    assert subir(web, "f.pdf", b"no es un pdf").status_code == 400
    assert not web.uploads.exists() or not list(web.uploads.iterdir())


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext no está instalado")
def test_un_pdf_se_enmascara_se_extrae_y_deja_el_contrato_sin_guardar_el_pdf(web):
    pdf = pdf_minimo([(50, 780, "Titular: Ana Ejemplo"), (50, 760, "Energia P1 8 kWh 0,20"),
                      (50, 740, "Potencia P1 4 kW")])
    subir(web, "consumo.csv", CSV_BUENO)
    r = subir(web, "factura.pdf", pdf)
    assert r.status_code == 200 and r.json()["ok"] is True
    enviado = str(web.ia.peticiones[0].texto)
    assert "Ana Ejemplo" not in enviado and "Energia P1" in enviado
    assert sorted(p.name for p in web.uploads.iterdir()) == ["consumo.csv", "contrato.yaml"]
    html = web.get("/ahorro/").content.decode()
    assert "4,99" in html and "No se puede" not in html


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext no está instalado")
def test_una_factura_que_no_cuadra_va_a_revision_y_no_cambia_el_contrato(web):
    web.ia.datos = {**FACTURA_IA, "total": "9.99"}
    r = subir(web, "factura.pdf", PDF_DE_LUZ)
    assert r.status_code == 422 and r.json()["ok"] is False and r.json()["problemas"]
    assert not (web.uploads / "contrato.yaml").exists()


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext no está instalado")
def test_si_el_consumo_no_cuadra_con_la_factura_no_se_muestra_el_ahorro(web):
    subir(web, "consumo.csv", CSV_DOBLE)
    subir(web, "factura.pdf", PDF_DE_LUZ)
    html = web.get("/ahorro/").content.decode()
    assert "no coincide" in html and 'id="resultados"' not in html


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext no está instalado")
def test_sin_clave_de_enmascarado_o_sin_ia_el_pdf_no_sale_y_el_aviso_es_claro(web):
    pdf = PDF_DE_LUZ
    with override_settings(MASK_KEY=""):
        r = subir(web, "f.pdf", pdf)
    assert r.status_code == 503 and "ESTALVIA_MASK_KEY" in r.json()["mensaje"] and not web.ia.peticiones
    web.ia.error = ErrorIA("sin conexión con la API")
    r = subir(web, "f.pdf", pdf)
    assert r.status_code == 422 and "IA" in r.json()["mensaje"]


def test_las_subidas_estan_ignoradas_por_git():
    r = subprocess.run(["git", "check-ignore", "-q", "data/private/uploads/consumo.csv"], cwd=RAIZ)
    assert r.returncode == 0


def test_las_paginas_traen_la_zona_de_arrastre_y_su_script_se_sirve_sin_html_inline(web):
    for ruta in ("/", "/ahorro/"):
        html = web.get(ruta).content.decode()
        assert 'id="zona"' in html and 'type="file"' in html and "csrfmiddlewaretoken" in html
        assert "<script>" not in html  # la CSP solo admite scripts propios
    js = web.get("/static/js/subir.js")
    assert js.status_code == 200 and "innerHTML" not in b"".join(js.streaming_content).decode()


def test_un_cuerpo_mas_grande_que_el_maximo_se_rechaza_antes_de_leerlo(web):
    r = web.post("/subir/", {"fichero": SimpleUploadedFile("f.pdf", b"%PDF-" + b"0" * 10)},
                 CONTENT_LENGTH=str(50 * 1024 * 1024))
    assert r.status_code == 413


def test_las_lineas_de_excedentes_o_compensacion_no_cuentan_como_precio_de_energia():
    f = datos_factura()
    extra = f.conceptos + [type(f.conceptos[0])(nombre="Compensación excedentes energía P1", precio=D("0.05"),
                                                  importe=D("-1"))]
    assert contrato_desde_factura(f.model_copy(update={"conceptos": extra})).precios.energia_eur_kwh["P1"] == D("0.20")


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext no está instalado")
def test_un_pdf_que_no_parece_una_factura_de_luz_no_sale_hacia_la_ia(web):
    r = subir(web, "otro.pdf", pdf_minimo([(50, 780, "Recibo de la comunidad de vecinos 45,00 EUR")]))
    assert r.status_code == 422 and "no se envía a la IA" in r.json()["mensaje"] and not web.ia.peticiones
