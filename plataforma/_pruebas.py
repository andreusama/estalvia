"""Arranque de Django para los tests de la plataforma (proceso aparte del de los tests del copiloto energético)."""

import os

CLAVE = "contrasena-de-prueba-no-real"


def preparar():
    os.environ.update(
        {"DJANGO_SETTINGS_MODULE": "plataforma.settings", "SECRET_KEY": "s" * 40, "ESTALVIA_PASSWORD": CLAVE}
    )
    import django

    django.setup()
