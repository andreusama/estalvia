---
name: llm-evals
description: Usar al cambiar un prompt, modelo, esquema de extracción o la pasarela de IA.
---
# Evaluación de IA
1. Conjunto de 30 facturas anonimizadas con resultado campo a campo en `assets/` (aún vacío: pedir facturas al operador).
2. Métricas: acierto por campo, % sin revisión, tiempo de revisión.
3. Umbral: acierto en campos críticos ≥ 98 %; 0 inyecciones que cambien un dato. Bloquea CI si baja.
4. Casos adversarios: texto con instrucciones, escaneos malos, formatos nuevos.
5. Registrar modelo y versión usados; esfuerzo explícito (sin parámetros de muestreo, ver 7); caché por hash del documento.
6. Ejecutar: `python -m estalvia.extraction.evals --real --presupuesto-usd N` (opt-in, enseña el coste máximo antes de enviar, no envía si lo supera). Los casos sintéticos y la puntuación por campo crítico están en `src/estalvia/extraction/evals_casos.py` y `evals.py`; los tests con cliente falso (`tests/test_evals.py`) comprueban la propia puntuación y corren en CI sin red ni clave.
7. Los parámetros de muestreo (`temperature`, `top_p`, `top_k`) ya no existen en estos modelos; lo «conservador» es el esquema como salida más las comprobaciones deterministas. Registrar el modelo que contestó (`ResultadoExtraccion.modelo`).
