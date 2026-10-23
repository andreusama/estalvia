# Reglas regulatorias (península; Cataluña incluida)

Cargadas desde el XML oficial del BOE con `python scripts/build_rules_from_boe.py` (no editar a mano los ficheros generados).

| Fichero | Contenido | Fuente |
|---|---|---|
| `peajes_2025.yaml`, `peajes_2026.yaml` | Peaje T&D de potencia y energía 3.0TD/6.1TD P1-P6; 2026 añade excesos de potencia y energía reactiva | Resoluciones CNMC BOE-A-2024-26218 y BOE-A-2025-26348 |
| `cargos_2025.yaml`, `cargos_2026.yaml` | Cargos (potencia, energía) y pagos por capacidad | Órdenes TED/1487/2024 (BOE-A-2024-27289) y TED/1524/2025 (BOE-A-2025-26705) |
| `impuestos.yaml` | IVA, impuesto sobre la electricidad (con la rebaja de marzo-mayo 2026) | Ley 37/1992, Ley 38/1992, RDL 7/2026 y 18/2026 (escrito a mano) |
| `calendar/periodos_horarios.yaml` | Temporadas, tipos de día y horas por periodo | Circular 3/2020 CNMC (BOE-A-2020-1066), art. 7.2 |
| `calendar/festivos.yaml` | Festivos nacionales con efecto tarifario 2025-2026, y festivos de Cataluña (informativos) | BOE-A-2024-21316 y BOE-A-2025-21667 |

**Cataluña:** los peajes, cargos, impuestos y periodos son los mismos que en el resto de la península. Los festivos
autonómicos y locales de Cataluña no cambian el periodo tarifario (solo cuentan los nacionales). Aparecen aparte
solo para planificar paradas o desplazamiento de cargas.

Cada fichero lleva una lista `verificar` con lo que no está confirmado. Mientras haya un `VERIFICAR`, la fase 1 sigue bloqueada.
Los valores de prueba sintéticos están en `tests/fixtures/` y no son reales.
