# Referencias oficiales de consumo para comparar (ticket #34)

Fecha de la investigación: 2026-10-29. Objetivo: poner en perspectiva el consumo de un cliente frente a consumidores parecidos
(tarifa de acceso, potencia contratada, tipo de suministro), **solo con fuente oficial citable**. Regla del TDD: no se inventa
ninguna media. Lo no confirmado va marcado `VERIFICAR`. No hay cifras de ninguna factura ni CSV propios en este documento.

## Conclusión

1. **Hoy se puede mostrar, con respaldo:** el consumo medio por punto de suministro (MWh/año) según **segmento** (doméstico, pyme,
   industrial) y **comunidad autónoma**, y según **peaje** (2.0TD, 3.0TD…). Fuente: estadísticas del mercado minorista de la CNMC.
2. **No existe (no encontrado) en fuente oficial:** consumo medio por **tramo de potencia contratada**. Es la comparación que
   se pedía. La CNMC publica la potencia contratada media de 2.0TD en un boletín (`VERIFICAR`, solo visto en un resultado de
   búsqueda), pero no el consumo por tramo de potencia.
3. **Con más datos del cliente se afina:** para viviendas, IDAE da el consumo mensual medio por superficie y por tener ACS o
   calefacción eléctricas. Habría que pedir esos dos datos al usuario.
4. **Límite importante:** son medias aritméticas de todos los suministros del segmento, incluidas segundas viviendas y
   suministros casi sin uso. La media no es lo «normal» y la mediana no se publica. El texto del informe debe decir «media de los
   suministros de tu tipo», nunca «consumes más/menos de lo normal», y no valorar al cliente como bueno o malo.

## Fuentes

### 1. CNMC, Estadísticas del mercado minorista de electricidad (la principal)

- Organismo: Comisión Nacional de los Mercados y la Competencia.
- Documento: «Estadísticas mercado minorista electricidad (4T2025)», fichero XLSX, datos «hasta diciembre 2025», publicado en la
  página el 15 de julio de 2026 (la cabecera de la página también muestra «19 Feb 2026»: fecha inconsistente, `VERIFICAR`).
- Página: <https://www.cnmc.es/estadistica/estadisticas-mercado-minorista-de-electricidad>
- Fichero: <https://www.cnmc.es/sites/default/files/editor_contenidos/Energia/Estadisticas/Estad%C3%ADsticas%20mercado%20minorista%20electricidad%204t2025.xlsx>
- Fuente declarada en el fichero: Circular 1/2005, de 30 de junio, de la CNE (petición de información a los distribuidores).
- Notas del fichero: la energía es la del **año móvil que termina el último día del semestre**; los puntos de suministro son los
  de la **fecha de fin del semestre**.
- Hojas útiles (verificadas leyendo el fichero):

| Hoja | Contenido | Serie |
|---|---|---|
| Tab3 | Energía suministrada (MWh) por peaje (2.0TD, 3.0TD, 6.1TD…) | desde 2021 |
| Tab 6 | Número de puntos de suministro por peaje | desde 2021 |
| Tab2 / Tab 5 | Energía y suministros por segmento (doméstico, pyme, industrial) | desde 2020 |
| Tab 7 / Tab8 | Energía y suministros por comunidad autónoma y provincia | desde 2019 |
| Tab11 | Consumo (MWh) y suministros por comunidad y segmento | desde 2022 |
| **Tab 12** | **Consumo medio (MWh) por suministro, por comunidad autónoma y segmento** | desde 2022 |

- Valores de ejemplo (públicos, tomados del fichero; MWh por suministro y año, «Año 2025 S2»):
  - Total España: doméstico 2,637 · pyme 42,39 · industrial 984,7.
  - Cataluña: doméstico 2,804 · pyme 49,75 · industrial 2.853.
  - Cálculo propio a partir de Tab3 ÷ Tab 6 (2025_S2): 2.0TD ≈ 2,64 MWh por suministro y año; 3.0TD ≈ 42,6 MWh.
    Es un cálculo nuestro, no una cifra publicada: hay que rotularlo «calculado a partir de datos de la CNMC».
- Licencia / reutilización: la página no indica ninguna. **`VERIFICAR`** antes de copiar los datos al repositorio; mientras tanto, se
  pueden leer en línea o citar, no vendorizar.
- Limitación: el peaje 2.0TD mezcla viviendas y comercios pequeños, y las medias incluyen suministros con consumo casi nulo.

### 2. IDAE, Estudio de consumo y gasto energético de los hogares españoles (septiembre 2025)

- Organismo: IDAE, Departamento de Estudios y Gestión del Dato. NIPO 62925004X.
- URL: <https://www.idae.es/sites/default/files/estudios_informes_y_estadisticas/20250911_Estudio_CONSUMO_y_GASTO_ENERGETICO_HOGARES_espanoles.pdf>
- Da el **consumo mensual medio de electricidad de un hogar tipo**, segmentado por superficie (menor de 119 m² o más) y por tener o
  no ACS o calefacción eléctricas (cuatro perfiles, tabla 5.3), con el reparto mensual y el precio medio del kWh. **No usa la
  potencia contratada** como variable.
- Licencia: «Cualquier reproducción, parcial o total, de la presente publicación debe contar con la aprobación por escrito
  del IDAE». No vendorizar; citar con enlace. `VERIFICAR` si citar una cifra suelta necesita permiso.
- Año de los datos del estudio: `VERIFICAR` (se apoya en la EPF del INE; no se confirmó el año exacto).

### 3. IDAE, SPAHOUSEC III (enero 2026)

- Informe web: <https://informesweb.idae.es/spahousec-iii/index.php>; PDF: <https://www.idae.es/sites/default/files/documentos/publicaciones_idae/20260123_SPAHOUSEC_III.pdf>
  (el informe web enlaza también una descarga ZIP; contenido sin comprobar).
- Mediciones in situ de electricidad en un panel de viviendas (718 según una búsqueda; `VERIFICAR` en el PDF), doce meses desde el
  1 de octubre de 2021, y una encuesta a más de 6.800 hogares (dato de prensa especializada, `VERIFICAR`).
- No se verificaron cifras concretas de electricidad por hogar ni por potencia contratada: las páginas de resultados
  (`/informe.php`, `/encuesta.php`, `/mediciones.php`) no se leyeron. Datos de 2021: antiguos para precios, válidos para hábitos.
- La página no declara licencia de reutilización.

### 4. Datadis y el Ayuntamiento de Barcelona (datos abiertos)

- Conjunto: «Consumo de electricidad (MWh) por código postal, sector económico y tramo horario en la ciudad de Barcelona».
- URL: <https://datos.gob.es/es/catalogo/l01080193-consumo-de-electricidad-mwh-por-codigo-postal-sector-economico-y-tramo-horario>
- Publica el Ayuntamiento de Barcelona (Oficina Municipal de Dades) con datos de Datadis. Cobertura 2016-01 a 2025-11,
  actualización mensual, ficheros CSV por año (2019–2025). **Licencia CC BY 4.0** (la única fuente con licencia explícita).
- Limitación: solo la ciudad de Barcelona. Útil para comparar la **forma horaria** por sector económico y para un cliente de
  Barcelona. El significado exacto de «tramo horario» no se comprobó: `VERIFICAR`.
- Datadis ofrece además informes agregados públicos (según la OCU); no se encontró un desglose por potencia contratada ni por
  peaje. `VERIFICAR` en datadis.es.

### 5. Perfiles de consumo (Red Eléctrica y CNMC)

- Cada año REE propone y la CNMC informa los perfiles de consumo para los suministros sin medida horaria. Para 2026: propuesta de REE
  con entrada en la CNMC el 26 de noviembre de 2025 e informe de la CNMC del 18 de diciembre de 2025 (expediente INF/DE/298/25):
  <https://cnmc.es/sites/default/files/6340245.pdf>.
- Sirven como referencia de la **forma** de la curva (no del nivel de consumo). Los coeficientes no se extrajeron: `VERIFICAR`.
  Los perfiles se aplican a puntos tipo 4 y 5; un cliente con lectura horaria queda fuera de ese uso.

### Fuentes descartadas

- IDAE, SPAHOUSEC (informe de 2011, datos de 2010): consumo de **todas** las energías por hogar; no es electricidad y es antiguo.
- Blogs y webs comerciales que repiten cifras de IDAE o de la CNMC: no son fuente oficial.
- INE: no se encontró una cifra oficial de kWh eléctricos por hogar ni por potencia (el INE publica flujos físicos de energía,
  no electricidad por hogar). `VERIFICAR` por si existiese otra operación estadística.

## Qué se puede mostrar en la web (propuesta)

| Comparación | Fuente | Estado |
|---|---|---|
| «La media de los suministros domésticos de tu comunidad es X MWh/año» (o pyme) | CNMC Tab 12 | Se puede, citando la fuente; `VERIFICAR` licencia |
| «La media de los suministros con tu peaje (2.0TD/3.0TD) es X MWh/año» | CNMC Tab3 ÷ Tab 6 (cálculo propio) | Se puede, rotulado como cálculo |
| Consumo por tramo de potencia contratada | — | No existe en lo encontrado |
| Vivienda parecida por superficie y calefacción eléctrica | IDAE 2025, tabla 5.3 | Pide dos datos más; licencia `VERIFICAR` |
| Forma de la curva horaria frente a un perfil | CNMC/REE (perfiles) o Barcelona/Datadis | Posible; falta extraer y verificar |

## Datos que habría que pedir al cliente

- Tipo de suministro: doméstico o pyme (la factura suele indicar el peaje, no el segmento).
- Comunidad autónoma o provincia (el código postal está enmascarado hoy; habría que preguntarlo aparte).
- Viviendas: superficie y si el ACS o la calefacción son eléctricas.
- Negocios: actividad (CNAE). No se encontró referencia oficial por sector en lo revisado.

## Pendiente antes de construir nada

- Confirmar la licencia de reutilización de la CNMC (`VERIFICAR`).
- Leer las páginas de resultados de SPAHOUSEC III y la tabla 5.3 y siguientes del estudio IDAE 2025 para ver si dan electricidad
  por zona climática o tipo de vivienda con cifras citables.
- Decidir si basta la comparación de la CNMC (media por segmento y comunidad) o se quiere buscar un dato por potencia
  (por ejemplo pidiendo a la CNMC o a un distribuidor un agregado).
