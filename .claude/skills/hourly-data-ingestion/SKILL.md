---
name: hourly-data-ingestion
description: Usar al leer CSV de consumo horario de distribuidoras o precios horarios de mercado (REData/ESIOS).
---
# Ingesta horaria (fase 2, aún sin código)
1. Un lector por formato de distribuidora y un formato interno normalizado (instante con zona horaria, kWh, kVArh, real/estimada).
2. Instantes en Europe/Madrid con conversión explícita a UTC; días de 23 y 25 horas deben tener test.
3. Un hueco nunca se rellena en silencio: se marca y se informa. Lecturas estimadas se distinguen de las reales.
4. Precios: guardar fecha de captura; si la fuente falla, el análisis queda incompleto, nunca con valores supuestos.
5. Los formatos reales de cada distribuidora se documentan en `references/` con un ejemplo SINTÉTICO.
