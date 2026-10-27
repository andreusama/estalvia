"""Ajustes de la web local (spec #18, ticket #26). Solo 127.0.0.1, sin base de datos y sin modo debug.

Secretos y ruta del consumo vienen de `.env` (ignorado por git) o del entorno; si falta algo, no arranca.
"""
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from estalvia.ai.gateway import leer_env

BASE = Path(__file__).parent
_ENV = leer_env(BASE.parents[2] / ".env")  # raíz del repositorio, no el directorio actual


def _exigir(nombre: str, minimo: int) -> str:
    valor = _ENV.get(nombre, "")
    if len(valor) < minimo:
        raise ImproperlyConfigured(f"{nombre} falta o es demasiado corta (mínimo {minimo} caracteres) en .env")
    return valor


SECRET_KEY = _exigir("ESTALVIA_WEB_SECRET", 32)
WEB_PASSWORD = _exigir("ESTALVIA_WEB_PASSWORD", 12)
DATOS_CSV = _ENV.get("ESTALVIA_DATOS_CSV", "")
CONTRATO = _ENV.get("ESTALVIA_CONTRATO", "")
DATOS_LECTOR = _ENV.get("ESTALVIA_DATOS_LECTOR", "fecha_hora_kwh")
# Subidas desde la web (ticket #32): carpeta local ignorada por git; la IA solo ve texto enmascarado con esta clave.
UPLOADS_DIR = _ENV.get("ESTALVIA_UPLOADS", str(BASE.parents[2] / "data" / "private" / "uploads"))
CACHE_DIR = _ENV.get("ESTALVIA_CACHE", str(BASE.parents[2] / "data" / "private" / "cache"))  # respuestas de la IA
MASK_KEY = _ENV.get("ESTALVIA_MASK_KEY", "")
FABRICA_IA = None  # llamable que devuelve un ClienteIA; None = cliente real desde .env (los tests ponen uno falso)

DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
ROOT_URLCONF = "estalvia.web.urls"
INSTALLED_APPS = ["estalvia.web"]
DATABASES: dict = {}
USE_TZ = True
TIME_ZONE = "Europe/Madrid"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "estalvia.web.middleware.CabecerasDeSeguridad",
]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE / "templates"],
              "APP_DIRS": False, "OPTIONS": {"context_processors": []}}]

# Sesión en una cookie firmada: no hace falta base de datos. Sin HTTPS en local, la cookie no puede ser «Secure».
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 8 * 3600
CSRF_USE_SESSIONS = True
CSRF_COOKIE_SAMESITE = "Strict"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
X_FRAME_OPTIONS = "DENY"
