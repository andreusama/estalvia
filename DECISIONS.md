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
- **Precios (#5):** `PriceStore` guarda cada consulta como una *captura* con su fecha; `get(..., as_of=)` reproduce un análisis sin consultar la fuente; fuente caída o sin datos = resultado incompleto, nunca valores supuestos. Caché en memoria por ahora (persistencia con la capa de datos).
- **REData (verificado contra la respuesta real, 2026-10):** `GET apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real`, sin autenticación. La serie spot (id 600) llega **cuartohoraria** (96 valores/día) aunque se pida `time_trunc=hour`; el almacén conserva la resolución nativa y no promedia (decisión pendiente en los módulos de análisis).
- **VERIFICAR (#5):** unidad de la serie (se asume EUR/MWh), zona horaria de `start_date`/`end_date` (se envía hora de Madrid), límites de uso del API, condiciones de reutilización (la página de REData no las indica; las condiciones generales de REE piden citar www.ree.es y la fecha de última actualización) y qué hacer con revisiones de precios ya capturados (hoy: nueva captura con `refresh=True`).
- **Calidad de ingesta (#3):** `ingest_hourly` devuelve `Ingesta(lecturas, calidad)`. `huecos` lista solo las horas ausentes entre la primera y la última lectura; las horas que faltan en los extremos aparecen en `faltantes` del mes. Un mes es `completo` solo si no falta ninguna hora local (743/745 h en los meses de cambio de hora). Un instante que no es hora en punto se rechaza.
- **Precios (#5), tras la revisión:** una respuesta con huecos o que no llega al final del rango es incompleta y no se cachea; los errores HTTP 4xx (salvo 429) no se reintentan; las fechas deben llevar zona horaria; el resultado expone `paso` (15 min en REData) y `atribucion` (cita de REE).
- **Periodos y totales (#4):** `Ingesta.etiquetadas(cal)` y `Ingesta.totales_por_periodo(cal, desde, hasta)` usan la hora local de Madrid y el calendario de `rules/calendar/`. El rango es semiabierto `[desde, hasta)`, con zona horaria obligatoria; un rango vacío o inverso es error (una fecha de fin de factura inclusiva hay que convertirla en el instante siguiente). Solo se exige calendario de festivos de los años de las lecturas dentro del rango. La tabla es **solo península y solo 3.0TD/6.xTD**: nada en los datos impide pasar un fichero de otro sistema o de 2.0TD, así que el llamante debe asegurarlo.
