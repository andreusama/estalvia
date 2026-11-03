"""Acceso con cuentas de usuario: cerrado por defecto, sin sesión no se ve nada; registro solo con código."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from plataforma.settings_tests import CLAVE, CODIGO

pytestmark = pytest.mark.django_db


def cliente():
    return Client(HTTP_HOST="localhost")


def con_cuenta(nombre="ana"):
    get_user_model().objects.create_user(username=nombre, password=CLAVE)
    return cliente()


def test_sin_sesion_redirige_a_entrar():
    r = cliente().get("/bar/")
    assert r.status_code == 302 and r["Location"].startswith("/entrar/")
    assert r["X-Robots-Tag"] == "noindex, nofollow"


def test_contrasena_incorrecta_no_entra():
    c = con_cuenta()
    r = c.post("/entrar/", {"username": "ana", "password": "mala"})
    assert r.status_code == 200 and "no son correctos" in r.content.decode()
    assert c.get("/bar/").status_code == 302


def test_usuario_inexistente_no_entra():
    r = cliente().post("/entrar/", {"username": "nadie", "password": CLAVE})
    assert r.status_code == 200 and "no son correctos" in r.content.decode()


def test_entrar_con_cuenta_vuelve_a_donde_iba():
    c = con_cuenta()
    r = c.post("/entrar/", {"username": "ana", "password": CLAVE, "next": "/bar/"})
    assert r.status_code == 302 and r["Location"] == "/bar/"
    assert c.get("/bar/").status_code == 200


def test_no_redirige_a_otro_sitio():
    c = con_cuenta()
    r = c.post("/entrar/", {"username": "ana", "password": CLAVE, "next": "https://malo.example/"})
    assert r["Location"] == "/"


def test_portada_lista_el_bar_y_salir_cierra_la_sesion():
    c = con_cuenta()
    c.post("/entrar/", {"username": "ana", "password": CLAVE})
    assert "/bar/" in c.get("/").content.decode()
    c.post("/salir/")
    assert c.get("/").status_code == 302


def registrar(c, codigo=CODIGO, nombre="beto", clave="una-clave-larga-1", repetida=None):
    return c.post(
        "/registro/",
        {"username": nombre, "password1": clave, "password2": repetida or clave, "codigo": codigo, "next": "/bar/"},
    )


def test_registro_con_el_codigo_crea_la_cuenta_y_entra():
    c = cliente()
    r = registrar(c)
    assert r.status_code == 302 and r["Location"] == "/bar/"
    assert get_user_model().objects.filter(username="beto").exists() and c.get("/bar/").status_code == 200


def test_registro_con_codigo_malo_no_crea_nada():
    c = cliente()
    r = registrar(c, codigo="adivinando")
    assert r.status_code == 200 and "código de invitación no es correcto" in r.content.decode()
    assert not get_user_model().objects.exists() and c.get("/bar/").status_code == 302


def test_registro_rechaza_contrasena_corta_o_distinta():
    assert "demasiado corta" in registrar(cliente(), clave="corta1").content.decode()
    assert "no coinciden" in registrar(cliente(), repetida="otra-clave-larga-2").content.decode()
    assert not get_user_model().objects.exists()


def test_registro_no_repite_nombre_de_usuario():
    con_cuenta("beto")
    assert "Ya existe" in registrar(cliente()).content.decode()


@override_settings(ESTALVIA_CODIGO_INVITACION="")
def test_sin_codigo_configurado_el_registro_esta_cerrado():
    r = registrar(cliente())
    assert r.status_code == 403 and not get_user_model().objects.exists()
