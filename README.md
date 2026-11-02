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

Root Directory `.`; Vercel detecta `manage.py`, ejecuta `build.py` (migra si hay `DATABASE_URL`) y sirve la función con hasta 120 s (`vercel.json`).
Variables de entorno:

| Variable | Para qué |
|---|---|
| `SECRET_KEY` o `ESTALVIA_WEB_SECRET` | Django, 32+ caracteres. Sin ella el despliegue falla a propósito. |
| `ESTALVIA_PASSWORD` o `ESTALVIA_WEB_PASSWORD` | Contraseña única. Sin ella nadie puede entrar. |
| `DATABASE_URL` | PostgreSQL (Neon u otro; la integración de Vercel Marketplace la crea). Sin ella el Bar avisa de que falta la base de datos. |
| `ANTHROPIC_API_KEY` | Lectura de documentos con la IA (Sonnet). Sin ella los documentos quedan «No se pudo leer». |
| `ALLOWED_HOSTS` | Solo si usas dominio propio (separado por comas). |

## Bar: probar con documentos reales

```
.venv/bin/python manage.py migrate
.venv/bin/python manage.py procesar_carpeta ruta/a/fotos    # sube y lee una carpeta (o un archivo) sin pasar por la web
DEBUG=1 .venv/bin/python manage.py runserver                 # y entra en /bar/
```
Los originales y las lecturas se guardan en la base de datos (`db.sqlite3` en local, ignorada por git). Los tests no llaman a la IA.
