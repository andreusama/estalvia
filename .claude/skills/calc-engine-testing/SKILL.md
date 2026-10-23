---
name: calc-engine-testing
description: Usar al escribir o modificar el motor de cálculo `src/estalvia/engine` o sus pruebas.
---
# Pruebas del motor
1. El motor es puro: sin Django, sin IA, sin BD. `Decimal`, nunca `float`.
2. Cada fórmula: test unitario con cálculo hecho a mano en el comentario. Verifica la aritmética a mano antes de culpar al motor.
3. Propiedades con hypothesis: más kWh no baja la energía; total = suma de líneas; cambiar vigencia solo cambia lo afectado.
4. Facturas de referencia (golden) anonimizadas en `tests/golden/`: total ≤ 0,5 % y por concepto en tolerancia pactada. Un cambio que altera una golden se explica por escrito y lo aprueba el operador.
5. Las reglas de prueba son sintéticas (`tests/fixtures/`), nunca valores regulatorios reales presentados como tales.
6. Comando: `pytest --cov=estalvia.engine --cov-fail-under=90`.
7. Pendiente: segunda implementación independiente (hoja de cálculo) para comparar.
