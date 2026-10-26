"""Web local (spec #18, ticket #26): acceso, 127.0.0.1, CSP y gráficos sin red. Sin base de datos, datos SINTÉTICOS."""
import os
import re
import tempfile
from pathlib import Path

import django
import pytest

CLAVE_WEB = "contrasena-de-prueba-no-real"
_TMP = tempfile.mkdtemp()
CSV = Path(_TMP) / "consumo-sintetico.csv"
CSV.write_text("date;hour;kwh\n" + "".join(f"2026-06-08;{h};1,5\n" for h in range(1, 25)), encoding="utf-8")
os.environ.update({"DJANGO_SETTINGS_MODULE": "estalvia.web.settings", "ESTALVIA_WEB_PASSWORD": CLAVE_WEB,
                   "ESTALVIA_WEB_SECRET": "s" * 40, "ESTALVIA_DATOS_CSV": str(CSV)})
django.setup()

from django.core.management import CommandError, call_command  # noqa: E402
from django.test import Client  # noqa: E402


def cliente(**kw):
    return Client(HTTP_HOST="127.0.0.1", **kw)


def entrar(c=None, clave=CLAVE_WEB):
    c = c or cliente()
    return c, c.post("/login/", {"password": clave})


def test_sin_sesion_se_redirige_al_login():
    r = cliente().get("/")
    assert r.status_code == 302 and r["Location"].startswith("/login/")


def test_con_la_contrasena_correcta_se_ve_la_curva_horaria_y_con_otra_no():
    c, r = entrar()
    assert r.status_code == 302
    pagina = c.get("/")
    assert pagina.status_code == 200 and b'id="datos-curva"' in pagina.content
    _, mala = entrar(clave="otra-cosa")
    assert mala.status_code == 200 and b"incorrecta" in mala.content
    assert cliente().get("/").status_code == 302


def test_cinco_fallos_bloquean_el_acceso_un_rato_incluso_con_la_clave_buena():
    from estalvia.web import views
    views.FALLOS.clear()
    c = cliente()
    for _ in range(5):
        c.post("/login/", {"password": "mala"})
    assert c.post("/login/", {"password": CLAVE_WEB}).status_code == 429
    views.FALLOS.clear()


def test_el_formulario_exige_token_csrf():
    c = cliente(enforce_csrf_checks=True)
    assert c.post("/login/", {"password": CLAVE_WEB}).status_code == 403


def test_cabeceras_de_seguridad_y_csp_estricta_sin_dominios_externos():
    c, _ = entrar()
    r = c.get("/")
    assert r["Content-Security-Policy"] == (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
    assert r["X-Content-Type-Options"] == "nosniff" and r["Referrer-Policy"] == "no-referrer"
    assert r["X-Frame-Options"] == "DENY" and "no-store" in r["Cache-Control"]


def test_la_pagina_no_referencia_nada_externo_ni_scripts_en_linea():
    c, _ = entrar()
    html = c.get("/").content.decode()
    assert not re.search(r"https?://", html)
    for etiqueta in re.findall(r"<script[^>]*>", html):
        assert 'src="/static/' in etiqueta or 'type="application/json"' in etiqueta


def test_los_ficheros_estaticos_son_una_lista_cerrada():
    c = cliente()
    assert c.get("/static/vendor/chart.umd.js").status_code == 200
    assert c.get("/static/js/curva.js").status_code == 200
    for malo in ["/static/../settings.py", "/static/%2e%2e/settings.py", "/static/vendor/otra.js"]:
        assert c.get(malo).status_code == 404


def test_un_host_ajeno_da_400():
    assert Client(HTTP_HOST="evil.example").get("/login/").status_code == 400


@pytest.mark.parametrize("direccion", ["0.0.0.0:8000", "0.0.0.0", "192.168.1.5:8000", "[::]:8000", "example.com:80"])
def test_runserver_rechaza_cualquier_direccion_que_no_sea_local(direccion):
    with pytest.raises(CommandError, match="127.0.0.1"):
        call_command("runserver", direccion)


def test_runserver_rechaza_ipv6():
    with pytest.raises(CommandError, match="127.0.0.1"):
        call_command("runserver", "8000", use_ipv6=True)


def test_no_hay_modo_debug_ni_base_de_datos():
    from django.conf import settings
    assert settings.DEBUG is False
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.dummy"


def test_chart_js_es_el_fichero_exacto_de_npm_anotado_en_vendor():
    import hashlib
    vendor = Path(__file__).parents[1] / "src/estalvia/web/static/vendor"
    nota = (vendor / "VENDOR.md").read_text(encoding="utf-8")
    assert hashlib.sha256((vendor / "chart.umd.js").read_bytes()).hexdigest() in nota


def test_salir_cierra_la_sesion_solo_por_post():
    c, _ = entrar()
    assert c.get("/logout/").status_code == 405
    assert c.post("/logout/").status_code == 302
    assert c.get("/").status_code == 302
