# Estalvia

Plataforma de prototipos de IA para pymes. Un solo proyecto Django (`plataforma/`) que monta cada prototipo como app bajo su prefijo
(`prototipos/<nombre>/`) y se despliega como un único proyecto de Vercel (`docs/adr/0001-una-plataforma-un-proyecto-vercel.md`).

Prototipos (cada uno es una herramienta aparte, con su app, su glosario y sus tests):
- **Bar** (`/bar/`): albaranes y facturas de proveedores, qué está pagado y qué no cuadra. Glosario: `prototipos/bar/GLOSSARY.md`.
- **Birròmetro** (`/birrometro/`): cuánto se gana con cada barril de cerveza (zurritos, cañas y jarras), sin IA. Glosario: `prototipos/birrometro/GLOSSARY.md`.

## Local

```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env    # rellenar SECRET_KEY (y ESTALVIA_CODIGO_INVITACION si quieres invitar)
DEBUG=1 .venv/bin/python manage.py runserver    # http://localhost:8000
.venv/bin/pytest && .venv/bin/ruff check .
```

## Vercel

Root Directory `.`; Vercel detecta `manage.py`, ejecuta `build.py` (migra si hay `DATABASE_URL`) y sirve la función con hasta 120 s (`vercel.json`).
Variables de entorno:

| Variable | Para qué |
|---|---|
| `SECRET_KEY` o `ESTALVIA_WEB_SECRET` | Django, 32+ caracteres. Sin ella el despliegue falla a propósito. |
| `ESTALVIA_CODIGO_INVITACION` | Código para crear cuenta en `/registro/`. Sin él el registro está cerrado. |
| `DATABASE_URL` | PostgreSQL (Neon u otro; la integración de Vercel Marketplace la crea). Sin ella el Bar avisa de que falta la base de datos. |
| `ANTHROPIC_API_KEY` | Lectura de documentos con la IA (Sonnet). Sin ella los documentos quedan «No se pudo leer». |
| `ALLOWED_HOSTS` | Solo si usas dominio propio (separado por comas). |

## Cuentas de usuario
Cada persona tiene su cuenta y ve solo lo suyo (`docs/adr/0002-cuentas-de-usuario-y-datos-por-usuario.md`).
```
.venv/bin/python manage.py crear_usuario nombre             # crea la cuenta (pide la contraseña)
.venv/bin/python manage.py crear_usuario nombre --adoptar   # además se queda con lo subido antes de las cuentas
```
Para invitar a alguien: pon `ESTALVIA_CODIGO_INVITACION` en Vercel y dale el enlace de `/registro/` y el código.
Contra la base de Vercel, el mismo comando con `DATABASE_URL=… .venv/bin/python manage.py crear_usuario …`.

## Bar: probar con documentos reales

```
.venv/bin/python manage.py migrate
.venv/bin/python manage.py procesar_carpeta ruta/a/fotos --usuario nombre    # sube y lee una carpeta (o un archivo) sin pasar por la web
DEBUG=1 .venv/bin/python manage.py runserver                 # y entra en /bar/
```
Los originales y las lecturas se guardan en la base de datos (`db.sqlite3` en local, ignorada por git). Los tests no llaman a la IA.

### Bar: pagos con el extracto del banco
En `/bar/pagos/` se sube el CSV del banco (se lee con reglas, sin IA). Antes de la primera vez, abre «Formato» y ajusta los
nombres de columna, el formato de fecha y los separadores a tu banco. Los extractos reales no van a git (`extracto*.csv`
está en `.gitignore`); los tests usan extractos inventados.
