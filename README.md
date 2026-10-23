# EstalvIA — copiloto energético para pymes agroalimentarias

Implementación del TDD (`TDD – Copiloto energético ... (MVP).md`). Principio: la IA lee y explica; el código calcula.

```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest --cov=estalvia.engine
.venv/bin/python scripts/validate_rules.py rules
```
Estado y pendientes: `DECISIONS.md`. Skills de desarrollo: `.claude/skills/`.
