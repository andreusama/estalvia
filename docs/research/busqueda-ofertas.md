# Búsqueda automática de ofertas de otras comercializadoras (ticket #35)

Fecha de la investigación: 2026-10-29. Objetivo: saber si EstalvIA puede, a partir de la curva de consumo del cliente, **buscar ofertas
de otras comercializadoras** sin que el cliente las teclee, y con qué condiciones. Regla del TDD: no se inventa ningún dato; lo no
confirmado va como `VERIFICAR`. Este documento no contiene cifras de ninguna factura ni CSV propios. Las cifras de precios que
aparecen son **públicas, de la web de cada comercializadora, con su fecha**, y solo sirven para ver la forma de los datos.

## Conclusión

1. **El comparador de la CNMC no ofrece API ni descarga de ofertas.** Un usuario pidió en datos.gob.es el histórico de ofertas del
   comparador (17/09/2025) y la CNMC respondió que «los datos que se solicitan no forman parte del catálogo de datos abiertos» y
   remitió al buzón del comparador. Estado de la petición: «Asignado».
2. **Automatizar el acceso al comparador no está autorizado.** El aviso legal de la sede de la CNMC solo autoriza «el uso
   estrictamente privado y para fines docentes o de investigación del material protegido, siempre y cuando se cite la fuente»; la
   «reproducción, distribución, comercialización o transformación no autorizadas» es infracción. No dice nada del acceso
   automatizado (ni lo permite ni lo prohíbe), pero un servicio comercial que extrae ofertas **no encaja en el uso autorizado**.
   Decisión: **no se hace scraping del comparador.** (El aviso legal es el de la sede electrónica; que el comparador tenga otro
   texto propio es `VERIFICAR`.)
3. **Las comercializadoras publican sus precios en abierto, pero sin formato común ni condiciones de reutilización.** Cada web es
   distinta, cambia sin avisar y mezcla precios con promociones. Ninguna de las revisadas declara licencia de reutilización de
   sus precios.
4. **Lo que sí está documentado y es oficial:** la CNMC define por resolución (BOE-A-2022-16989) el enlace/QR de la factura que
   abre el comparador con los datos del cliente. Es una vía **iniciada por el cliente** y sirve como puente (ver «Propuesta»).
5. **Recomendación:** una vía en tres tiempos: (a) preguntar a la CNMC por escrito (lo envía el cliente o el responsable, no el
   agente); (b) mientras tanto, un **catálogo de ofertas mantenido a mano**, con fecha y fuente, de pocas comercializadoras; (c) valorar
   un servicio de datos con licencia si el producto lo justifica. Ver «Tickets propuestos».

## 1. Comparador de la CNMC

- URL: <https://comparador.cnmc.gob.es/>. Es una aplicación web que se maneja con JavaScript: el usuario elige el tipo de suministro,
  introduce datos y obtiene ofertas. No se envió ningún dato ni formulario durante esta investigación.
- Contacto publicado: `info.comparador@cnmc.es`.
- Aviso legal de la sede: <https://sede.cnmc.gob.es/politica-privacidad-y-aviso-legal>. Cláusulas relevantes (sección «Propiedad
  intelectual e industrial»): titularidad de la CNMC; uso privado, docente o de investigación con cita de la fuente; reproducción,
  distribución, comercialización o transformación no autorizadas, infracción. En la sección de responsabilidad: la CNMC no responde
  de enlaces a terceros. **No hay cláusula sobre reutilización, scraping, robots ni sobre el comparador.**
- Datos abiertos: la petición <https://datos.gob.es/es/solicitud-de-datos/historico-de-ofertas-del-comparador-de-ofertas-de-la-cnmc>
  confirma que las ofertas no están en el catálogo de datos abiertos de la CNMC.
- Alcance: electricidad en baja tensión y gas natural. Según un informe de la CNMC de 2016 (citado en una búsqueda, `VERIFICAR`), el
  PVPC no se incluye en el comparador por depender del precio horario de mercado.

### El enlace/QR de la factura (BOE-A-2022-16989)

- Resolución de la CNMC que fija el contenido del QR/enlace de la factura. **Solo cubre consumidores con peaje 2.0TD**; 3.0TD queda fuera.
- Estructura: `https://comparador.cnmc.gob.es/comparador/QRE?parametro1=valor1&parametro2=valor2...` (orden y mayúsculas de las claves
  no importan; se incluyen solo los parámetros que aplican).
- Parámetros (según la resolución):
  - Obligatorios: `cp` (código postal), `pP1`, `pP2` (potencia contratada, kW), `caP1`, `caP2`, `caP3` (consumo del último año por
    periodo, kWh) con `iniA` (inicio de ese consumo), `tc` (tipo de contrato), `finContrato`, `tf` (tipo de factura), `iniF`, `finF`,
    `fFact`, `pmaxP1`, `pmaxP2`, `cups`, `com` (comercializadora), `rev`.
  - Condicionales: consumos y importes de la factura (`cfP1..3`, `imp`, `impPot`, `impEner`, ...), precios (`prP1`, `prP2`, `prE1..3`),
    `finPen`, `dtoBS`, `verde`, `promo`.
  - `tc`: dos caracteres; el primero A–H (A = PVPC, H = tarifa plana…), el segundo indica cuota fija mensual.
- La resolución **no** obliga a las comercializadoras a entregar sus ofertas por una vía estructurada: de ahí que el comparador no
  publique un fichero de ofertas.
- Implicación de privacidad: el enlace lleva datos del cliente en la propia URL (incluido el CUPS). EstalvIA **no debe** construir ese
  enlace con CUPS ni con nombre; la regla del proyecto es no poner datos personales en URL.

## 2. Comercializadoras revisadas (web pública)

Lectura de la web el 2026-10-29. «Ficha» = si hay un documento de precios con fecha de vigencia.

| Comercializadora | Qué publica | Formato | Vigencia | Ficha/PDF | Condiciones de uso de los datos |
|---|---|---|---|---|---|
| Som Energia | Tarifa 2.0TD: energía P1/P2/P3 y potencia por año; indexada y de generación enlazadas | Tabla HTML | «válidos a partir del 1 de octubre de 2026» | PDF de condiciones generales (precios en la web) | Sin declaración de reutilización |
| Octopus Energy | Flexi (indexada), Relax (precio único) y Octopus 3 (P1/P2/P3); potencia en €/kW/mes | HTML | **No consta**; solo «precio calculado para 30 días» y 12 meses | Sin PDF; enlace a términos HTML | No se leyeron sus términos (`VERIFICAR`) |
| Naturgy | Por Uso (precio único de energía fijo 12 meses, 2.0TD sin bono social) | Web y PDF de condiciones | No leída la página oficial (la URL probada dio 404) | Condiciones generales y particulares en PDF | No leídas |
| Endesa | Varias ofertas 2.0TD (Tempo 24h, One Luz…) con energía con y sin descuento y potencia en €/kW·día | HTML y PDF promocionales | PDF de One Luz con ventana de contratación caducada | PDF por oferta | No leídas |
| Iberdrola | Plan Estable y otros; precios de energía incluyen peaje 2.0TD, potencia en €/kW·día | HTML (los campos de precio no se extrajeron) | «tarifas vigentes mayo 2026» | No localizada | No leídas |

No revisadas por error de acceso (HTTP 403 y 404): Holaluz y Repsol.

Observaciones:

- Para Naturgy, Endesa e Iberdrola solo se obtuvieron cifras de **comparadores de terceros**, que **se contradicen entre sí**
  (hasta ~0,05 €/kWh de diferencia en un mismo producto). No se usan: un precio sin fuente primaria fechada no entra al catálogo.
- Las webs comerciales mezclan precio normal y promoción (descuento del primer año, saldo de bienvenida, requisitos de factura
  electrónica o domiciliación). El modelo debe guardar **el precio regular** y registrar la promoción aparte, sin calcular ahorro con
  ella (decisión pendiente, ver «Brechas»).
- Hay 625 comercializadoras de electricidad en España según una búsqueda (cifra de prensa, `VERIFICAR`): un catálogo propio
  completo no es viable; sí lo es uno acotado a las más relevantes o a las que el cliente nombre.

## 3. Correspondencia con el modelo de #21

`OfertaFija(energia_eur_kwh por periodo, potencia_eur_kw_anio por periodo, capturada, fuente)` y
`OfertaIndexada(margen_eur_kwh, potencia_eur_kw_anio, otros_eur_kwh|None, capturada, fuente)`.

| Dato publicado | Campo del modelo | Estado |
|---|---|---|
| Energía por periodo (P1/P2/P3) | `energia_eur_kwh` | Cubierto. Una oferta de precio único se rellena con el mismo valor en P1, P2 y P3. |
| Potencia en €/kW·año | `potencia_eur_kw_anio` | Cubierto. |
| Potencia en €/kW·día o €/kW·mes | `potencia_eur_kw_anio` | Conversión explícita: ×12 (mes) o × días del año (día). Hay que fijar la regla (¿365 o 366?) y anotarla: `VERIFICAR`. |
| Servicios de ajuste fuera del precio (Som Energia: 0,025 €/kWh en su indexada) | `otros_eur_kwh` | Cubierto: es el dato explícito que pide el aviso de #21. |
| Margen de una indexada | `margen_eur_kwh` | Cubierto si la comercializadora lo publica; Octopus Flexi muestra un precio de referencia, no el margen. No se puede deducir: marcar sin calcular. |
| Cuota fija diaria o mensual (Octopus Flexi: gestión en €/día; `tc` con cuota fija) | — | **Brecha**: el modelo no tiene término fijo. |
| Descuento de primer año, saldo, regalos | — | **Brecha**: no se modela; no entran en el ahorro. |
| Permanencia, penalización, duración del precio | — | **Brecha**: texto informativo; no cambia el importe pero sí la recomendación. |
| Exigencias (factura electrónica, domiciliación) | — | Informativo. |
| Fecha de vigencia | `capturada` | Parcial: se guarda cuándo se copió, no hasta cuándo vale. Falta `vigente_desde`. |
| Potencia de 3.0TD (P1–P6) | `potencia_eur_kw_anio` | El modelo la admite, pero **no se encontró ninguna fuente de ofertas 3.0TD** en esta investigación. |

## 4. Servicios con licencia

- No se encontró ninguna **API pública** de ofertas en los comparadores privados (Selectra / Tarifasgasluz, Comparadorluz, Watiofy
  describen un servicio al consumidor; ninguno anuncia acceso programático ni licencia de datos). Cualquier acuerdo sería
  comercial y a medida: habría que preguntar por escrito sobre precio, cobertura (¿incluye 3.0TD y pymes?), frecuencia de
  actualización y si permite mostrar resultados a nuestros clientes.
- Riesgo de conflicto de interés: los comparadores privados cobran comisión de las comercializadoras. El TDD fija que en v1 **no hay
  comisiones de terceros**; un servicio así debe poder entregarse sin condicionar el orden de los resultados.

## 5. Propuesta

1. **Puente inmediato, sin tocar el dato de nadie:** un botón «Compara en el comparador de la CNMC» en el informe que abra el
   comparador en el navegador del cliente (sin enviar nada por EstalvIA). Dos variantes:
   - enlace simple a `https://comparador.cnmc.gob.es/`, sin datos (sin riesgo);
   - enlace con los parámetros del QR (`cp`, `pP1`, `pP2`, `caP1..3`, `tc`…) **sin `cups`**. Lo decide el cliente pulsando; aun así
     son datos suyos en la URL. **Pendiente de decisión del responsable** y de confirmar `VERIFICAR` que el comparador acepta un
     enlace sin `cups`. Solo 2.0TD.
   El cliente trae después las ofertas que elija a EstalvIA (ticket #29, formulario manual) para que el motor las recalcule.
2. **Pregunta a la CNMC** (la envía una persona, no el agente) a `info.comparador@cnmc.es`: ¿existe fichero o API de ofertas?, ¿bajo qué
   condiciones se pueden reutilizar?, ¿se admite acceso automatizado?, ¿el enlace del QR funciona sin `cups`?, ¿cubre 3.0TD?
3. **Catálogo de ofertas a mano**: un fichero versionado (`ofertas/`), de las comercializadoras que cada cliente tenga como candidatas,
   con precio regular, vigencia, fuente (URL y fecha) y quién la capturó. Se cae si la oferta caduca. Solo con fuente primaria.
4. **Servicio con licencia**: consultar a uno o dos proveedores (ver sección 4) cuando haya cliente que lo pida.

## 6. Tickets propuestos

- **Texto y botón de comparación con la CNMC en el informe** (enlace simple primero; variante con parámetros tras la decisión del
  responsable). Depende de #33.
- **Ampliar el modelo de oferta**: cuota fija, `vigente_desde`/`vigente_hasta`, permanencia y promoción como dato informativo
  (sin entrar en el cálculo). Amplía #21.
- **Catálogo de ofertas con fuente** y pruebas de que ninguna oferta sin fuente o caducada entra en una recomendación.
- **HUMAN**: escribir a la CNMC (preguntas del punto 2 de la propuesta).
- **HUMAN o investigación**: contactar con comparadores/proveedores de datos con licencia y pedir condiciones.
- **Revisión legal** antes de cualquier recomendación de cambio de comercializadora (guardarraíles: lenguaje de «estimación», sin
  prometer ahorro, no actuar como comercializadora ni asesor regulado).

## Pendiente de verificar

- El texto legal propio del comparador (no solo el de la sede) y si prohíbe el acceso automatizado.
- Condiciones de uso web de Octopus, Naturgy, Endesa, Iberdrola, Holaluz y Repsol (no leídas o no accesibles).
- Precios oficiales vigentes de Naturgy, Endesa e Iberdrola (solo había fuentes de terceros contradictorias).
- Etiqueta de potencia de Som Energia: la web rotula «P3 Valle» en la potencia, pero 2.0TD solo tiene dos periodos de potencia.
- Regla de conversión de potencia diaria a anual (365 o 366 días).
- Si algún comparador privado ofrece acceso por API y en qué condiciones.
- Cifras de prensa (625 comercializadoras, 333 distribuidoras).
