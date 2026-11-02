"""Ajustes de la plataforma Estalvia (un solo proyecto de Vercel; ver docs/adr/0001).

Secretos y contraseña vienen del entorno (Vercel) o de `.env` en local. Sin base de datos todavía: las sesiones van
firmadas en la cookie. Si falta SECRET_KEY no arranca; si falta la contraseña, el acceso queda cerrado (nunca abierto).
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _cargar_env_local(ruta: Path) -> None:
    """Lee KEY=valor de un `.env` local sin pisar lo que ya venga del entorno (en Vercel no existe el fichero)."""
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, _, valor = linea.partition("=")
            os.environ.setdefault(clave.strip(), valor.strip().strip("'\""))


_cargar_env_local(BASE_DIR / ".env")

EN_VERCEL = bool(os.environ.get("VERCEL"))
DEBUG = os.environ.get("DEBUG") == "1" and not EN_VERCEL

SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("ESTALVIA_WEB_SECRET", "")  # acepta ambos nombres
if len(SECRET_KEY) < 32:
    if DEBUG:
        SECRET_KEY = "solo-para-desarrollo-local-" + "x" * 16
    else:
        raise ImproperlyConfigured("SECRET_KEY (o ESTALVIA_WEB_SECRET) falta o tiene menos de 32 caracteres")

# Contraseña única de la plataforma (usuarios reales vendrán después). Vacía = nadie entra.
ESTALVIA_PASSWORD = os.environ.get("ESTALVIA_PASSWORD") or os.environ.get("ESTALVIA_WEB_PASSWORD", "")

ALLOWED_HOSTS = [".vercel.app", "localhost", "127.0.0.1"] + [
    h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h
]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "plataforma",
    "prototipos.bar",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "plataforma.acceso.ExigeContrasena",
]
ROOT_URLCONF = "plataforma.urls"
WSGI_APPLICATION = "plataforma.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
            ]
        },
    }
]
DATABASES: dict = {}  # PostgreSQL llegará con los modelos (docs/adr/0002 del bar)

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = EN_VERCEL
if EN_VERCEL:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Castellano, preparado para catalán (aún sin ficheros .po)
LANGUAGE_CODE = "es"
LANGUAGES = [("es", "Castellano"), ("ca", "Català")]
LOCALE_PATHS = [BASE_DIR / "locale"]
FORMAT_MODULE_PATH = ["plataforma.formats"]
USE_I18N = True
USE_THOUSAND_SEPARATOR = True  # 1.240,00 € también con cuatro cifras
TIME_ZONE = "Europe/Madrid"
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # Vercel ejecuta collectstatic solo si está definido
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
