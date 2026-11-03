import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from plataforma.settings_tests import CLAVE


def usuario(nombre="ana"):
    return get_user_model().objects.get_or_create(username=nombre)[0]


def cliente_de(nombre):
    """Un navegador con la sesión de ese usuario."""
    u = usuario(nombre)
    u.set_password(CLAVE)
    u.save()
    c = Client(HTTP_HOST="localhost")
    assert c.login(username=nombre, password=CLAVE)
    return c


@pytest.fixture
def web():
    return cliente_de("ana")
