# Decisiones

- **2026-10-22 — Alcance inicial:** fase 0 completa (estructura, CI, 8 skills, datos sintéticos) y núcleo de la fase 1
  (RuleSet versionado y motor para potencia, energía, IE, alquiler, IVA). Las fases 2-6 no están empezadas.
- **2026-10-22 — Reglas reales cargadas** (península y Cataluña) desde el XML del BOE: peajes y cargos 2025-2026 de 3.0TD y 6.1TD,
  excesos de potencia y reactiva 2026, IVA/IE, periodos horarios y festivos. Cataluña no tiene reglas propias: usa las mismas
  y sus festivos no alteran los periodos. Los valores de peajes y cargos coinciden con totales publicados por una comercializadora
  (tests/test_real_rules.py).
- **Aún sin cubrir:** 2027 (sin publicar al cargar), excesos de potencia 2025 (Anexo II modificado por BOE-A-2025-5341),
  IEE de agosto-septiembre 2026 (RDL 18/2026, depende del IPC), festivos de 2027 en adelante, resto de tarifas (2.0TD, 6.2TD+).
- **El motor aún no usa peajes/cargos:** `calcular_factura` espera reglas `potencia_eur_kw_anio` y `energia_eur_kwh`. Falta decidir
  (VERIFICAR con facturas reales) cómo se suman peaje + cargo + pago por capacidad + margen/energía del contrato en cada línea.
- **Python:** el TDD pide ≥3.12; el entorno local tiene 3.10, así que el código es compatible con 3.10 y el CI usa 3.12. VERIFICAR.
- **Pendiente de VERIFICAR en el motor:** prorrateo en bisiestos (hoy día a día sobre los días del año de cada fecha),
  excesos de potencia, energía reactiva, qué conceptos entran en cada base, redondeo por comercializadora, periodos horarios 3.0TD/6.1TD.
- **Fuera de esta entrega:** Django/Celery/PostgreSQL, lectores CSV por distribuidora, conector de precios, llamada real al LLM, informe PDF, panel.
- **Sin repositorio git:** la carpeta no lo es; `git init` cuando quieras.

- **Ingesta horaria (#2):** el formato interno es CSV `instante,kwh,kvarh,tipo` con instante ISO 8601 con desfase UTC. Los valores negativos se aceptan (exportación o compensación): VERIFICAR la regla con datos reales. El parámetro `reader` del seam llega con los lectores por distribuidora.
