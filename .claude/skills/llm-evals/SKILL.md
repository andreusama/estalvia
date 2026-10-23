---
name: llm-evals
description: Usar al cambiar un prompt, modelo, esquema de extracción o la pasarela de IA.
---
# Evaluación de IA
1. Conjunto de 30 facturas anonimizadas con resultado campo a campo en `assets/` (aún vacío: pedir facturas al operador).
2. Métricas: acierto por campo, % sin revisión, tiempo de revisión.
3. Umbral: acierto en campos críticos ≥ 98 %; 0 inyecciones que cambien un dato. Bloquea CI si baja.
4. Casos adversarios: texto con instrucciones, escaneos malos, formatos nuevos.
5. Registrar modelo y versión usados; parámetros conservadores; caché por hash del documento.
