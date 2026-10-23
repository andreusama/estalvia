# Formato `fecha_hora_kwh` (export de un portal de comercializadora)

Ejemplo SINTÉTICO (valores inventados; el fichero real de una persona no se guarda en el repositorio):

```
date;hour;kwh
2026-09-01;1;0,125
2026-09-01;2;0,5
...
2026-09-01;24;1,0
```

- Separador `;`, coma decimal, líneas CRLF, fecha local de Madrid, hora 1-24.
- **La hora N es el intervalo que termina en N**: hora 1 = 00:00-01:00. Verificado en privado contra una factura real (los totales por periodo coinciden exactamente; la otra lectura no).
- No trae kVArh ni marca real/estimada: quedan `None` y `desconocida`, nunca 0 ni "real".
- Días de cambio de hora (23 y 25 horas): **sin verificar** con un fichero real de este portal. El lector acepta las horas 1..horas reales del día; una hora fuera es error y una hora ausente sale como hueco.
- Lector: `ingest_hourly(datos, lector="fecha_hora_kwh")`. Código: `src/estalvia/ingestion/hourly.py`.
