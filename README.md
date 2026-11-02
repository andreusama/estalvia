# Estalvia

Plataforma de prototipos de IA para pymes. Un solo proyecto Django (`plataforma/`) que monta cada prototipo como app bajo su prefijo
(`prototipos/<nombre>/`) y se despliega como un único proyecto de Vercel (`docs/adr/0001-una-plataforma-un-proyecto-vercel.md`).

Prototipo actual: **Bar** (`/bar/`): albaranes y facturas de proveedores, qué está pagado y qué no cuadra. Glosario: `prototipos/bar/GLOSSARY.md`.

## Local

```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env    # rellenar SECRET_KEY y ESTALVIA_PASSWORD
DEBUG=1 .venv/bin/python manage.py runserver    # http://localhost:8000
.venv/bin/pytest && .venv/bin/ruff check .
```

## Vercel

Root Directory `.`; Vercel detecta `manage.py`. Variables de entorno obligatorias: `SECRET_KEY` o `ESTALVIA_WEB_SECRET` (32+ caracteres)
y `ESTALVIA_PASSWORD` o `ESTALVIA_WEB_PASSWORD`. Sin la primera el despliegue falla a propósito; sin la segunda nadie puede entrar.
Para un dominio propio, añadir `ALLOWED_HOSTS` (separado por comas). Pendiente: PostgreSQL, Blob y `ANTHROPIC_API_KEY`
llegan con los modelos y la extracción.
