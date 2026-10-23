---
name: security-privacy-review
description: Usar antes de integrar cualquier cambio que toque datos de clientes, ficheros subidos, logs, secretos, dependencias o IA.
---
# Revisión de seguridad y privacidad
Lista (TDD sección 12):
- [ ] Toda consulta nueva filtra por organización.
- [ ] Sin datos personales ni CUPS completo en logs o errores.
- [ ] Todo texto al proveedor de IA pasa por la pasarela (`ai/masking.py`).
- [ ] Ficheros subidos validados (tipo real, tamaño, antivirus) y procesados aislados, sin red.
- [ ] Sin secretos en código ni datos de prueba.
- [ ] Dependencias analizadas (`pip-audit`), versiones fijadas.
- [ ] Pruebas de aislamiento entre clientes en verde.
Datos de ejemplo: solo sintéticos o anonimizados.
