"""Ajustes para pytest: entorno controlado, base de datos en memoria y ninguna llamada real a la IA."""

import os

CLAVE = "contrasena-de-prueba-no-real"
CODIGO = "codigo-de-invitacion-de-prueba"
os.environ.update(
    {"SECRET_KEY": "s" * 40, "ESTALVIA_CODIGO_INVITACION": CODIGO, "ANTHROPIC_API_KEY": "", "DATABASE_URL": ""}
)
os.environ.pop("VERCEL", None)

from .settings import *  # noqa: E402, F401, F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # rápido; solo en tests
