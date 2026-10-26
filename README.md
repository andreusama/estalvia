# EstalvIA — copiloto energético para pymes agroalimentarias

Implementación del TDD (`TDD – Copiloto energético ... (MVP).md`). Principio: la IA lee y explica; el código calcula.

```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest --cov=estalvia.engine
.venv/bin/python scripts/validate_rules.py rules
```
Estado y pendientes: `DECISIONS.md`. Skills de desarrollo: `.claude/skills/`.

## Web local

`python manage.py runserver` (solo escucha en 127.0.0.1:8000). Necesita en `.env`: `ESTALVIA_WEB_SECRET` (32+ caracteres),
`ESTALVIA_WEB_PASSWORD` (12+) y `ESTALVIA_DATOS_CSV` (ver `.env.example`). Sin base de datos; el consumo se lee del CSV.
