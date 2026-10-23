# Copiloto energético

Servicio que lee facturas de luz y consumos horarios de una pyme, recalcula la factura con reglas versionadas y devuelve un informe de ahorro verificable. La IA lee y explica; el código calcula.

## Language

### Tiempo y periodos

**Periodo facturado**:
El intervalo de fechas que cubre una factura.
_Avoid_: periodo (a secas), billing period, ciclo

**Periodo tarifario**:
Cada uno de los tramos horarios con precio propio de una tarifa de acceso: P1 a P6 en 3.0TD y 6.xTD, P1 a P3 de energía en 2.0TD.
_Avoid_: periodo (a secas), franja, tramo horario

### Consumo

**Lectura horaria**:
El consumo de una hora concreta (kWh y, si existe, kVArh), tal como llega en un fichero de consumo.
_Avoid_: lectura (a secas), medición horaria

**Lectura del contador**:
El valor acumulado del contador, inicial y final, que imprime la factura por periodo tarifario.
_Avoid_: lectura (a secas), medida

### Extracción de facturas

**Campo crítico**:
Dato de una factura sin el cual no se puede recalcular: potencia contratada, kWh por periodo tarifario, importes y fechas.
_Avoid_: campo importante, campo clave

**Comprobación determinista**:
Regla escrita en código que valida los datos extraídos de una factura, sin intervención de la IA. Una diferencia de hasta 0,02 € en las sumas no cuenta como fallo; cualquier otro incumplimiento sí.
_Avoid_: validación (a secas), check

**Revisión**:
El estado de una factura que ha fallado una comprobación determinista y espera corrección humana.
_Avoid_: a revisar (estado técnico), pendiente
