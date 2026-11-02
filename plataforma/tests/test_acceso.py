"""Acceso con contraseña única: cerrado por defecto, sin sesión no se ve nada."""

from django.test import Client, override_settings

from plataforma._pruebas import CLAVE


def cliente():
    return Client(HTTP_HOST="localhost")


def test_sin_sesion_redirige_a_entrar():
    r = cliente().get("/bar/")
    assert r.status_code == 302 and r["Location"].startswith("/entrar/")
    assert r["X-Robots-Tag"] == "noindex, nofollow"


def test_contrasena_incorrecta_no_entra():
    c = cliente()
    r = c.post("/entrar/", {"password": "mala"})
    assert r.status_code == 200 and "no es correcta" in r.content.decode()
    assert c.get("/bar/").status_code == 302


def test_contrasena_correcta_entra_y_vuelve_a_donde_iba():
    c = cliente()
    r = c.post("/entrar/", {"password": CLAVE, "next": "/bar/"})
    assert r.status_code == 302 and r["Location"] == "/bar/"
    assert c.get("/bar/").status_code == 200


def test_no_redirige_a_otro_sitio():
    r = cliente().post("/entrar/", {"password": CLAVE, "next": "https://malo.example/"})
    assert r["Location"] == "/"


@override_settings(ESTALVIA_PASSWORD="")
def test_sin_contrasena_configurada_nadie_entra():
    r = cliente().post("/entrar/", {"password": ""})
    assert r.status_code == 503


def test_portada_lista_el_bar_y_salir_cierra_la_sesion():
    c = cliente()
    c.post("/entrar/", {"password": CLAVE})
    assert "/bar/" in c.get("/").content.decode()
    c.post("/salir/")
    assert c.get("/").status_code == 302
