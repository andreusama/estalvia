# EstalvIA

Plataforma de prototipos de IA para pymes: un proyecto Django (`plataforma/`) con una app por prototipo en `prototipos/<nombre>/`.
Primer prototipo: **Bar** (albaranes y facturas de proveedores a partir de fotos). Decisiones del sistema en `docs/adr/`; las del
prototipo en `prototipos/bar/docs/adr/`. Reglas duras: ningún importe lo calcula la IA (la IA lee, el código calcula y compara, sin
tolerancia), nada se da por bueno sin revisión humana, y solo imágenes sintéticas o respuestas de IA falsas en los tests y en git
(excepción de datos reales: `prototipos/bar/docs/adr/0001-fotos-reales-a-terceros.md`). Comandos: ver `README.md`.

## Agent skills

### Issue tracker

Issues y tickets viven en GitHub Issues de la cuenta `andreusama` (CLI `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Etiquetas por defecto: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-contexto: `GLOSSARY-MAP.md` en la raíz apunta a un `GLOSSARY.md` por prototipo; ADR de sistema en `docs/adr/`. See `docs/agents/domain.md`.
