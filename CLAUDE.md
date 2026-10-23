# EstalvIA

Copiloto energético para pymes agroalimentarias. La especificación es `TDD – Copiloto energético para pymes agroalimentarias (MVP).md`;
estado y decisiones en `DECISIONS.md`. Reglas duras del TDD: no inventar datos regulatorios (un `VERIFICAR` sin resolver bloquea la fase),
ningún importe lo calcula la IA, y solo datos sintéticos o anonimizados en desarrollo. Comandos: ver `README.md`.

## Agent skills

### Issue tracker

Issues y tickets viven en GitHub Issues de la cuenta `andreusama` (CLI `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Etiquetas por defecto: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: un `GLOSSARY.md` y `docs/adr/` en la raíz. See `docs/agents/domain.md`.
