# EstalvIA — copiloto energético para pymes agroalimentarias

Implementación del TDD (`TDD – Copiloto energético ... (MVP).md`). Principio: la IA lee y explica; el código calcula.

```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest --cov=estalvia.engine
.venv/bin/python scripts/validate_rules.py rules
```
Estado y pendientes: `DECISIONS.md`. Skills de desarrollo: `.claude/skills/`.

## Web local

`python manage_energia.py runserver` (solo escucha en 127.0.0.1:8000; `manage.py` es ahora el de la plataforma). Necesita en `.env`: `ESTALVIA_WEB_SECRET` (32+ caracteres),
`ESTALVIA_WEB_PASSWORD` (12+) y `ESTALVIA_DATOS_CSV` (ver `.env.example`). Sin base de datos; el consumo se lee del CSV.

## Plataforma (Bar y futuras apps) — Vercel

Un solo proyecto de Vercel con una app Django por prototipo bajo su prefijo (`/bar/`); ver `docs/adr/0001-una-plataforma-un-proyecto-vercel.md`.

Local: `SECRET_KEY` y `ESTALVIA_PASSWORD` en `.env` (ver `.env.example`), luego `DEBUG=1 .venv/bin/python manage.py runserver` y abrir http://localhost:8000.
Tests (proceso aparte de los del copiloto, que fijan otros ajustes): `.venv/bin/python -m pytest plataforma prototipos`.

Vercel: Root Directory `.` (el de la raíz del repo), sin Framework Preset a mano (detecta `manage.py`). Variables de entorno obligatorias:
`SECRET_KEY` o `ESTALVIA_WEB_SECRET` (32+ caracteres) y `ESTALVIA_PASSWORD` o `ESTALVIA_WEB_PASSWORD`. Sin la primera el despliegue falla a propósito; sin la segunda nadie puede entrar.
Para un dominio propio, añadir `ALLOWED_HOSTS` (separado por comas). Pendiente: PostgreSQL, Blob y `ANTHROPIC_API_KEY` llegan con los modelos y la extracción.
