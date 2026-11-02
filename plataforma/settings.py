"""Ajustes de la plataforma Estalvia (un solo proyecto de Vercel; ver docs/adr/0001).

Secretos y contraseña vienen del entorno (Vercel) o de `.env` en local. Sin base de datos todavía: las sesiones van
firmadas en la cookie. Si falta SECRET_KEY no arranca; si falta la contraseña, el acceso queda cerrado (nunca abierto).
"""

import os
import urllib.parse
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


def _base_de_datos() -> dict:
    """PostgreSQL con DATABASE_URL (Vercel, Neon); SQLite en local; en Vercel sin URL, sin base de datos."""
    url = os.environ.get("DATABASE_URL", "")
    if url:
        u = urllib.parse.urlparse(url)
        opciones = {
            k: v for k, v in urllib.parse.parse_qsl(u.query) if k in ("sslmode", "channel_binding", "connect_timeout")
        }
        return {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": u.path.lstrip("/"),
                "USER": urllib.parse.unquote(u.username or ""),
                "PASSWORD": urllib.parse.unquote(u.password or ""),
                "HOST": u.hostname,
                "PORT": u.port or 5432,
                "OPTIONS": opciones,
                "CONN_MAX_AGE": 0,
                "DISABLE_SERVER_SIDE_CURSORS": True,
            }
        }
    if EN_VERCEL:
        return {}
    return {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}


DATABASES = _base_de_datos()

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
