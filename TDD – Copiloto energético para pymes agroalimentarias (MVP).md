# TDD – Copiloto energético para pymes agroalimentarias (MVP)

Oct 22, 2026 · @Andres

## 1. Resumen y alcance

El MVP es un servicio que recibe la factura de luz (PDF) y el consumo horario de una pyme agroalimentaria y devuelve un informe de ahorro verificable, con cada importe recalculado por código y explicado en lenguaje sencillo.

- **Qué hace:** extrae los datos de la factura, recalcula la factura con un motor determinista, detecta sobrecostes (potencia contratada, energía reactiva, tarifa, picos de consumo) y simula alternativas.
- **Para quién:** empresas con cámaras frigoríficas, envasado, bombeo, invernaderos o ganadería, con suministro en alta o baja tensión de potencia superior a 15 kW (tarifas 3.0TD y 6.1TD).
- **Qué entrega:** un informe de una página para el cliente y un panel interno para el operador que revisa y valida.
- **Qué no hace:** no controla equipos, no cambia contratos y no actúa como comercializadora ni como representante del cliente.
- **Principio rector:** la IA lee y explica; el código calcula. Ningún importe lo genera un modelo de lenguaje.

**Cómo debe usar este documento el agente de desarrollo**

1. Leer las secciones en orden y trabajar por fases (sección 14), con criterios de aceptación en cada una.
2. No inventar datos regulatorios (precios, periodos, fórmulas). Si falta un dato, dejar el campo vacío, marcarlo con `VERIFICAR` y pedirlo.
3. Crear primero las skills de la sección 10; después, el código.
4. Trabajar solo con datos sintéticos o anonimizados. Nunca con datos reales de clientes en desarrollo.

Ámbito inicial: suministros peninsulares. Quedan fuera Canarias, Baleares, Ceuta, Melilla, el gas y los clientes domésticos.

## 2. Objetivos y no-objetivos

El MVP debe demostrar que puede recalcular una factura real con precisión y encontrar ahorro verificable en al menos 3 de 5 clientes piloto.

**Objetivos medibles** (valores propuestos; el operador debe confirmarlos antes de la fase 1)

| Objetivo | Métrica | Umbral propuesto |
| --- | --- | --- |
| Recalcular la factura | Diferencia entre el total recalculado y el de la factura | ≤ 0,5 % del importe en el conjunto de prueba |
| Extraer los datos del PDF | Acierto en campos críticos (potencia, kWh por periodo, importes, fechas) | ≥ 98 % sobre 30 facturas anonimizadas |
| Rapidez | Tiempo desde la subida hasta el informe | < 5 minutos con revisión humana excluida |
| Trazabilidad | Importes del informe con regla, fecha de vigencia y cálculo asociados | 100 % |
| Valor para el piloto | Clientes con ahorro estimado positivo y explicado | ≥ 3 de 5 |

**No-objetivos de la v1**

- Controlar o automatizar equipos de la planta.
- Cambiar contratos o gestionar el cambio de comercializadora en nombre del cliente.
- Dar asesoramiento regulado o dimensionar instalaciones (por ejemplo, una batería de condensadores) sin un ingeniero.
- Facturas de gas, clientes domésticos y sistemas no peninsulares.
- Chat de preguntas libres con el cliente (posterior al MVP).

## 3. Usuarios, casos de uso y flujo principal

Hay dos usuarios: el operador, que prepara y valida los análisis, y el cliente, que aporta datos y recibe el informe.

| Usuario | Qué necesita | Permisos |
| --- | --- | --- |
| Operador | Subir datos, revisar la extracción, ver hallazgos, generar y enviar el informe | Acceso a todos los clientes que gestiona |
| Cliente (gerente o responsable de planta) | Entender cuánto paga de más y qué cambiar | Solo ve su organización y sus informes |
| Administrador | Gestionar reglas regulatorias y usuarios | Todo, con registro de auditoría |

**Flujo principal**

1. El operador crea la organización y registra la autorización firmada del cliente para usar sus datos.
2. Sube las facturas (PDF) de los últimos 12 meses y, si existe, el CSV de consumo horario.
3. El sistema extrae los campos con IA y los valida con reglas deterministas. Lo dudoso pasa a revisión humana.
4. El motor recalcula las facturas y ejecuta los módulos de análisis.
5. El operador revisa los hallazgos y genera el informe.
6. El cliente recibe el informe y puede descargarlo.

**Casos de uso del MVP**

- **CU1:** recalcular una factura y comprobar que coincide con la emitida.
- **CU2:** detectar potencia contratada sobredimensionada o con excesos.
- **CU3:** detectar penalizaciones por energía reactiva.
- **CU4:** comparar la modalidad de precio actual con alternativas.
- **CU5:** localizar picos de potencia y estimar el efecto de escalonar el arranque de equipos.

## 4. Arquitectura y stack

La v1 es un monolito Django modular con una cola de tareas, porque es lo más rápido de construir y de mantener para un equipo de una persona.

&#91;embedded content: arquitectura por capas · 5 capas, 12 componentes\]

La web encola el trabajo; los procesos extraen datos con IA y el motor de cálculo recalcula las facturas con las reglas y los precios, sin depender de la web ni de la IA.

| Componente | Responsabilidad | Tecnología propuesta |
| --- | --- | --- |
| Web y API | Autenticación, subida de ficheros, panel del operador, descarga de informes | Django y Django REST Framework |
| Tareas en segundo plano | Extracción, análisis y generación de informes | Celery o RQ con Redis |
| Base de datos | Datos estructurados, reglas y auditoría | PostgreSQL |
| Almacenamiento de ficheros | PDFs, CSV e informes, cifrados | Almacenamiento compatible con S3 en región UE |
| Módulo de extracción | PDF a texto (con OCR si es un escaneo), LLM a esquema JSON, validación | pdfplumber, OCR, pydantic |
| Pasarela de IA | Única puerta de salida al modelo; enmascara datos, valida la respuesta y registra el uso | Módulo propio |
| Motor de cálculo | Recálculo de facturas y simulaciones | Python puro, `Decimal`, pandas |
| Almacén de reglas | Precios regulados, periodos, impuestos y vigencias | Ficheros YAML o JSON versionados y tests |
| Conectores de precios | Precios horarios de mercado | REData o ESIOS de Red Eléctrica |
| Generador de informes | Informe HTML a PDF | WeasyPrint o similar |
| Observabilidad | Logs sin datos personales, errores, métricas | Sentry y logs estructurados |

**Decisiones de diseño**

- **Separación de responsabilidades:** el módulo de cálculo no importa nada de Django ni de IA. Recibe datos y reglas, y devuelve importes. Así se prueba solo.
- **Reproducibilidad:** cada análisis guarda la versión de las reglas, la de los datos de precios y el modelo de IA usado.
- **Región:** todo en la UE (hosting, almacenamiento y, si es posible, el proveedor de IA).
- **Multiinquilino:** cada organización aísla sus datos con filtros obligatorios por organización a nivel de consulta.
- **Lenguaje y versiones:** Python 3.12 o superior y una versión de Django con soporte vigente. VERIFICAR versiones al iniciar.

## 5. Modelo de datos

Hay 12 entidades principales; la regla es que ningún dato personal o sensible se guarda sin una razón y todos los cálculos quedan ligados a una versión de reglas.

| Entidad | Campos clave | Notas |
| --- | --- | --- |
| Organization | nombre, tipo, contacto, estado | Raíz del aislamiento multiinquilino |
| Authorization | organización, titular, alcance, fecha, documento firmado, caducidad | Sin autorización vigente no se procesan datos |
| Site | organización, CUPS (cifrado), tarifa, tensión, potencias contratadas por periodo | Un suministro por registro |
| Bill | site, periodo facturado, comercializadora, importes por concepto, total, fichero original, estado de revisión | Estados: subida, extraída, a revisar, validada |
| BillLine | bill, concepto, periodo tarifario, cantidad, precio, importe | Permite comprobar que la suma cuadra |
| HourlyReading | site, instante (con zona horaria), kWh, kVArh, tipo real o estimada | Índice por site e instante |
| PriceSeries | origen, instante, precio, fecha de captura | Se guarda la fecha de captura para reproducir el análisis |
| RuleSet | tipo, tarifa, valor, inicio y fin de vigencia, fuente normativa, hash | Versionado e inmutable una vez publicado |
| Analysis | site, ruleset, versión del modelo de IA, parámetros, estado | Un análisis es reproducible |
| Finding | analysis, módulo, descripción, ahorro estimado, intervalo, confianza, evidencia | La evidencia apunta a facturas y lecturas concretas |
| Report | analysis, versión, fichero, hash | Inmutable una vez enviado |
| AuditLog | usuario, acción, objeto, instante, origen | Nunca incluye contenido de las facturas |

**Reglas de datos**

- Los importes se guardan como `Decimal` con moneda y los instantes con zona horaria (Europe/Madrid) y conversión explícita a UTC.
- El CUPS y los NIF se cifran en reposo y se enmascaran en pantallas y registros.
- Cada registro tiene fecha de creación y de modificación, y se puede borrar por completo a petición del cliente (ver sección 13).

## 6. Ingesta de datos

Tres fuentes alimentan el sistema: las facturas en PDF, el consumo horario del contador y los precios horarios de mercado. Cada una se valida antes de usarse.

**6.1 Facturas en PDF**

1. Validar el fichero: tipo real (no solo la extensión), tamaño máximo, sin contraseña, escaneo antivirus.
2. Extraer el texto nativo; si el PDF es una imagen, aplicar OCR.
3. Enmascarar datos personales innecesarios antes de enviar nada al modelo de IA (dirección, nombre, NIF).
4. Pedir al modelo que devuelva un JSON que cumpla el esquema (abajo). Una respuesta que no valide se descarta.
5. Aplicar validaciones deterministas. Si alguna falla, la factura pasa a `a_revisar` y el operador la corrige.

Validaciones obligatorias:

- La suma de los conceptos coincide con el total, con tolerancia de 0,02 €.
- Las fechas del periodo son coherentes y no se solapan con otras facturas del mismo suministro.
- La potencia y los kWh están en rangos plausibles para la tarifa.
- Cada concepto pertenece a una lista conocida; los desconocidos se marcan.

Campos mínimos del esquema de extracción:

```json
{
  "comercializadora": "string",
  "cups": "string",
  "tarifa_acceso": "3.0TD | 6.1TD | otra",
  "modalidad_precio": "fijo | indexado | pvpc | desconocida",
  "periodo_facturado": {"inicio": "YYYY-MM-DD", "fin": "YYYY-MM-DD"},
  "potencia_contratada_kw": {"P1": 0, "P2": 0, "P3": 0, "P4": 0, "P5": 0, "P6": 0},
  "potencia_maxima_kw": {"P1": 0},
  "energia_kwh": {"P1": 0},
  "energia_reactiva_kvarh": {"P1": 0},
  "conceptos": [{"nombre": "string", "cantidad": 0, "precio": 0, "importe": 0}],
  "impuestos": {"electrico": 0, "iva": 0},
  "total": 0,
  "confianza_campos": {"campo": 0.0}
}
```

**6.2 Consumo horario**

- Aceptar el CSV que descargan los clientes de su distribuidora (Iberdrola, Endesa, Viesgo, EDP y otras) con un lector por formato, y un formato interno normalizado.
- Tratar los cambios de hora (días de 23 y 25 horas), los huecos y las lecturas estimadas frente a las reales. Un hueco nunca se rellena en silencio: se marca y se informa.
- La descarga automática desde Datadis queda para la fase 7 y exige autorización expresa del titular.

**6.3 Precios de mercado**

- Obtener los precios horarios de Red Eléctrica (REData y ESIOS; ESIOS pide un token gratuito) y guardarlos con su fecha de captura.
- Cachear, reintentar con retroceso y registrar errores. Si falla la fuente, el análisis que depende de ella se marca como incompleto, nunca se rellena con valores supuestos.

**6.4 Calendario**

- Mantener los festivos nacionales y autonómicos aplicables, porque determinan qué horas cuentan como valle en la tarifa.

## 7. Motor de cálculo

El motor calcula cada factura a partir de datos y de reglas con fecha de vigencia, sin acceso a base de datos ni a IA, y devuelve un desglose por concepto que se puede auditar.

**Principios**

- **Determinista y puro:** las mismas entradas dan siempre la misma salida.
- **Reglas fuera del código:** ningún precio regulado, porcentaje ni periodo se escribe a mano en el código. Todo se carga de un `RuleSet` versionado con fecha de inicio y de fin.
- **Trazable:** cada línea del desglose incluye la regla usada, su vigencia y la fuente normativa.
- **Decimales exactos:** `Decimal` con política de redondeo explícita; el redondeo de cada comercializadora se modela como parámetro.
- **Sin supuestos silenciosos:** si falta un dato, el motor devuelve un error claro y no un valor por defecto.

**Estructura general de la factura** (los conceptos que entran en cada base de impuestos hay que fijarlos con la normativa: VERIFICAR)

```latex
Base = T_{potencia} + T_{energia} + T_{excesos} + T_{reactiva} + T_{otros}

Total = (Base + IE + Alquiler) \times (1 + IVA)
```

| Concepto | Cálculo | A verificar con la normativa |
| --- | --- | --- |
| Término de potencia | Suma por periodo de la potencia contratada por el precio anual del periodo, prorrateado por los días facturados | Prorrateo en años bisiestos y precios de peajes, cargos y margen |
| Término de energía | Suma por periodo de los kWh por su precio; en indexado, suma hora a hora de los kWh por el precio horario más ajustes | Qué incluyen peajes y cargos y cómo se aplican los servicios de ajuste |
| Excesos de potencia | Fórmula normativa a partir de la demanda máxima medida en cada periodo | Fórmula, coeficientes y tarifas a las que aplica |
| Energía reactiva | Recargo si el factor de potencia (cos φ) baja del umbral; tramos por valor | Umbral, tramos, periodos a los que aplica y precios |
| Impuesto sobre la electricidad | Porcentaje sobre la base con un importe mínimo por MWh | Porcentaje y mínimo vigentes en cada fecha |
| Alquiler de equipos de medida | Importe fijo por día o mes | Lo que declara cada factura |
| IVA | Porcentaje sobre la base | Tipo vigente en cada fecha y condiciones |

**Por qué las reglas llevan fecha de vigencia.** La prensa ha informado en 2026 de cambios temporales en el IVA de la luz (entre el 10 % y el 21 %) y en el impuesto eléctrico (reducido al 0,5 %). El motor debe recalcular bien una factura de cualquier fecha, así que el valor correcto depende del día. Esos datos están sin confirmar: el agente debe verificarlos contra el BOE y la CNMC antes de cargarlos.

**Periodos horarios**

- Las tablas de periodos (horas, días laborables, fines de semana, festivos y meses) se cargan desde ficheros oficiales y se prueban contra casos conocidos.
- Como referencia, según la CNMC, en la tarifa 2.0TD la potencia punta va de 8 a 24 horas y la de valle de 0 a 8 horas y todos los fines de semana y festivos.
- Las tarifas 3.0TD y 6.1TD usan seis periodos con calendario por meses: cargar la tabla oficial, no deducirla.

**Contrato de la función principal**

```python
def calcular_factura(
    site: SiteParams,
    lecturas: Lecturas,
    reglas: RuleSet,
    periodo: Periodo,
) -> Desglose:
    """Devuelve lineas(concepto, base, precio, importe, regla_id, vigencia) y total."""
```

**Criterios de aceptación**

- Reproduce al menos 20 facturas reales anonimizadas con diferencia total ≤ 0,5 % y, en cada concepto, dentro de la tolerancia acordada.
- Pruebas de propiedades: más kWh nunca baja el término de energía; el total es la suma de las líneas; cambiar la fecha de vigencia cambia solo los conceptos afectados.
- Cobertura de pruebas del módulo de al menos 90 % (objetivo propuesto).
- Una regla sin fuente normativa registrada impide publicar el `RuleSet`.

## 8. Módulos de análisis y simulación

Cada módulo compara la factura recalculada con un escenario alternativo, y el ahorro es la diferencia entre ambos, siempre calculada por el motor.

| Módulo | Entradas | Salida | Criterio |
| --- | --- | --- | --- |
| A. Potencia contratada | Potencia contratada y demanda máxima por periodo, 12 meses | Potencia propuesta por periodo, coste de excesos y ahorro anual | Se recalcula la factura con la potencia propuesta incluyendo los excesos |
| B. Energía reactiva | kVArh y kWh por periodo, recargos facturados | Meses con recargo, coste anual y si conviene estudiar compensación | Solo informa. No dimensiona baterías |
| C. Modalidad de precio | Consumo horario y precios horarios | Coste con precio fijo, indexado y mixto para el mismo perfil | Compara con los mismos datos, con intervalo de incertidumbre |
| D. Picos y desplazamiento de carga | Consumo horario, equipos principales, restricciones del cliente | Reducción posible del pico en kW y ahorro anual por escalonar o mover cargas | Respeta ventanas y límites del cliente. Solo recomienda |
| E. Errores de facturación | Facturas, lecturas | Lecturas estimadas, cargos repetidos, periodos mal aplicados | Cada hallazgo lleva la factura y la línea concreta |

**Método común para estimar un ahorro**

1. Línea base: factura recalculada con la configuración actual durante 12 meses.
2. Escenario: la misma factura recalculada con el cambio propuesto.
3. Ahorro = línea base − escenario, anualizado.
4. Sensibilidad: repetir con supuestos más prudentes y más optimistas y mostrar el intervalo.
5. Confianza: alta, media o baja según la calidad de los datos (lecturas reales o estimadas, meses completos, reglas verificadas).

**Reglas de seguridad del producto**

- Nunca se recomienda algo que pueda dañar el producto o parar la planta sin que el cliente confirme sus límites (por ejemplo, temperaturas de las cámaras).
- Toda recomendación deja claro que es informativa y qué supuestos usa.
- Un hallazgo sin evidencia concreta no llega al informe.

## 9. Uso de IA: roles, límites y evaluación

El modelo de lenguaje hace dos trabajos, leer facturas y explicar resultados, y nunca calcula importes ni interpreta normativa por su cuenta.

**Roles permitidos**

| Rol | Qué hace | Salida esperada |
| --- | --- | --- |
| Extracción | Convierte el texto de una factura en datos estructurados | JSON que valida contra el esquema de la sección 6 |
| Normalización | Asocia los nombres de conceptos de cada comercializadora con los conceptos internos | Código de concepto o `desconocido` |
| Redacción del informe | Convierte hallazgos ya calculados en texto claro | Texto cuyas cifras salen solo de los datos suministrados |
| Asistente de preguntas (después del MVP) | Responde sobre un análisis concreto | Respuestas con referencia al dato |

**Límites obligatorios**

1. **Sin cálculo:** toda cifra del informe viene de campos estructurados. Un comprobador automático extrae los números del texto generado y falla si alguno no existe en los datos.
2. **Sin normativa de memoria:** el modelo no aporta reglas ni precios. Solo se usan los del `RuleSet`.
3. **Esquemas estrictos:** respuesta en JSON validado; si no valida, se reintenta una vez y después pasa a revisión humana.
4. **Baja variabilidad:** salida restringida a un esquema, comprobaciones deterministas sobre lo extraído, esfuerzo de razonamiento explícito y versión del modelo fijada y registrada en cada análisis (los parámetros de muestreo como `temperature` ya no existen en estos modelos).
5. **Documentos como datos:** el contenido de un PDF nunca se trata como instrucciones (ver sección 12, inyección de instrucciones).
6. **Sin acciones con efectos:** el modelo no tiene herramientas que envíen correos, modifiquen datos de clientes ni accedan a Internet.
7. **Minimización:** antes de enviar texto al proveedor, la pasarela enmascara nombres, direcciones y NIF, y limita el CUPS a lo estrictamente necesario.

**Proveedor de IA**

- Contrato de encargo de tratamiento firmado, región UE cuando sea posible y política de no entrenar con los datos del cliente.
- Retención mínima y registro de qué modelo y versión procesó cada documento.
- Plan de contingencia: la pasarela debe poder cambiar de proveedor sin tocar el resto del sistema.

**Evaluación**

- Conjunto de 30 facturas anonimizadas con el resultado correcto campo a campo, que crece con cada error real encontrado.
- Métricas: acierto por campo, porcentaje de facturas que pasan sin revisión y tiempo de revisión humana.
- Se ejecuta en CI ante cualquier cambio de prompt, de modelo o de esquema, y bloquea la integración si el acierto en campos críticos baja del umbral.
- Casos adversarios: facturas con texto que intenta dar instrucciones, escaneos de baja calidad y formatos nuevos.
- Control de coste: caché por hash del documento, límite de tokens y alerta si el gasto mensual supera el presupuesto.

## 10. Skills que debe crear el agente de desarrollo

Antes de escribir código, el agente crea ocho skills, que son carpetas de instrucciones que carga solo cuando la tarea las necesita, para no repetir contexto ni cometer errores regulatorios.

**Estructura de cada skill** (ajustar la ruta a la herramienta que se use)

```text
.claude/skills/<nombre>/
  SKILL.md        # nombre, descripción con cuándo usarla, procedimiento y listas de comprobación
  references/     # normativa citada, glosario, ejemplos
  scripts/        # utilidades ejecutables y verificables
  assets/         # plantillas y datos de prueba sintéticos
```

Cada `SKILL.md` empieza con un encabezado con `name` y `description`. La descripción dice cuándo debe activarse. Debe ser corto, con pasos numerados y enlaces a `references/` para los detalles.

| Skill | Cuándo se usa | Qué contiene |
| --- | --- | --- |
| `es-electricity-tariffs` | Al tocar tarifas, periodos, reglas o impuestos | Glosario (potencia, peajes, cargos, reactiva), cómo se estructura un `RuleSet`, cómo actualizarlo con fuente y vigencia, script que valida que no hay huecos ni solapes de vigencia |
| `bill-extraction` | Al crear o cambiar la extracción de facturas | Esquema JSON, validaciones deterministas, cómo añadir el formato de una comercializadora, plantilla de prueba con resultado esperado |
| `hourly-data-ingestion` | Al leer CSV de distribuidoras o precios | Formatos conocidos, cambios de hora, huecos, lecturas estimadas, unidades, script de normalización |
| `calc-engine-testing` | Al escribir o modificar el motor | Cómo escribir pruebas con facturas reales anonimizadas, tolerancias, pruebas de propiedades, política de redondeo |
| `llm-evals` | Al cambiar un prompt, un modelo o un esquema | Cómo añadir casos, ejecutar la evaluación, umbrales de paso y casos adversarios |
| `energy-report-writing` | Al redactar o cambiar el informe | Estructura de una página, tono, avisos obligatorios, comprobador de que cada cifra existe en los datos |
| `security-privacy-review` | Antes de cada integración | Lista de comprobación de la sección 12, enmascarado de datos personales, registros sin datos sensibles, secretos, dependencias |
| `legal-guardrails` | Al escribir textos para clientes, contratos o avisos | Frases permitidas y prohibidas (sin garantías de ahorro), textos de consentimiento, cuándo escalar a revisión humana. No sustituye a un abogado |

**Reglas de creación de skills**

1. La skill se escribe antes de usarla y se prueba con una tarea real pequeña.
2. Una skill no repite lo que ya está en este documento: lo referencia.
3. Los datos regulatorios dentro de una skill llevan fuente y fecha, y el script de verificación debe fallar si caducan.
4. Si el agente corrige un error por un dato desactualizado, actualiza la skill en la misma integración.
5. Los datos de ejemplo son siempre sintéticos o anonimizados.

**Permisos del agente de desarrollo**

- Puede leer y escribir en el repositorio y ejecutar pruebas.
- No tiene acceso a secretos de producción, a bases de datos de clientes ni a facturas reales.
- Toda integración pasa por revisión humana antes de publicarse.

## 11. Pruebas, evaluación y calidad

La regla es que ningún cambio llega a producción si empeora el acierto del cálculo o de la extracción, y las pruebas con facturas reales anonimizadas son la red de seguridad principal.

| Tipo | Qué cubre | Criterio de paso (propuesto) |
| --- | --- | --- |
| Unitarias | Cada fórmula del motor y cada conversión de datos | 100 % verdes; cobertura del motor ≥ 90 % |
| Facturas de referencia (golden) | Facturas completas con resultado esperado | Diferencia total ≤ 0,5 % y por concepto dentro de la tolerancia pactada |
| Propiedades | Invariantes del cálculo con datos generados al azar | Sin contraejemplos en 1.000 casos |
| Integración | Flujo completo: subida, extracción, análisis, informe | Sin errores y con la traza de auditoría completa |
| Evaluación de IA | Acierto de campos y casos adversarios (sección 9) | Acierto en campos críticos ≥ 98 %; 0 casos de inyección que cambien un dato |
| Seguridad | Aislamiento entre clientes, subida de ficheros, dependencias, secretos | Sin hallazgos críticos ni altos abiertos |
| Carga básica | Varias facturas y un año de datos horarios a la vez | Análisis en menos de 5 minutos |

**Datos de prueba**

- Un generador de facturas sintéticas con el resultado calculado por una segunda implementación independiente (por ejemplo, una hoja de cálculo), para detectar errores del motor.
- Facturas reales solo si están anonimizadas y con autorización escrita del cliente.
- Cada error encontrado en un piloto se convierte en un caso de prueba permanente.

**Definición de «hecho» para cualquier tarea**

1. Código con pruebas que fallan sin el cambio y pasan con él.
2. Integración continua en verde (pruebas, análisis estático, análisis de dependencias).
3. Skill relevante actualizada si el cambio afecta a reglas o procedimientos.
4. Revisión de seguridad con la lista de la sección 12 si toca datos, ficheros o IA.
5. Nota en el registro de cambios con la regla normativa afectada, si la hay.

## 12. Seguridad

Los activos a proteger son las facturas y los consumos de los clientes, que revelan cómo trabaja cada empresa, y la integridad de los informes que se les entregan.

**Modelo de amenazas y controles**

| Amenaza | Impacto | Controles |
| --- | --- | --- |
| Un cliente ve datos de otro | Fuga de datos y pérdida de confianza | Filtro obligatorio por organización en toda consulta, pruebas automáticas de aislamiento, roles mínimos |
| Fichero malicioso subido como factura | Ejecución de código o consumo de recursos | Validar el tipo real, límite de tamaño, análisis antivirus, procesar PDFs en un proceso aislado sin red y con tiempo máximo |
| Inyección de instrucciones en un PDF | El modelo cambia datos o revela información | Documentos tratados como datos, salidas validadas por esquema, sin herramientas con efectos, comprobación de cifras (sección 9) |
| Fuga hacia el proveedor de IA | Datos personales o confidenciales fuera de control | Enmascarado previo, contrato de encargo, región UE, sin entrenamiento con datos del cliente |
| Credenciales expuestas | Acceso no autorizado | Gestor de secretos, sin secretos en el repositorio, rotación, análisis de secretos en CI |
| Cuenta comprometida | Acceso a informes y datos | Autenticación de dos factores para operadores, sesiones cortas, límite de intentos, alertas de acceso inusual |
| Registros con datos sensibles | Fuga por logs y herramientas de errores | Logs sin contenido de facturas ni CUPS completo, filtros en Sentry |
| Cadena de suministro | Dependencia vulnerable o comprometida | Versiones fijadas, análisis de dependencias, lista de componentes (SBOM) |
| Abuso o coste descontrolado | Gasto elevado en el proveedor de IA | Cuotas por cliente, límites de tasa, alertas de presupuesto |
| Alteración de informes | Informe no fiable | Hash del informe, versión inmutable, registro de auditoría |
| Pérdida de datos | Incapacidad de servir al cliente | Copias de seguridad cifradas y probadas, plan de recuperación |

**Requisitos técnicos mínimos**

- Cifrado en tránsito (TLS 1.2 o superior) y en reposo (AES-256 o equivalente), con CUPS y NIF cifrados además a nivel de campo.
- Alojamiento en la UE y separación de entornos: el desarrollo nunca usa datos reales.
- Registro de auditoría de accesos, descargas y cambios, sin contenido de facturas.
- Retención limitada: borrado de ficheros y datos al terminar el encargo o cuando se solicite (ver sección 13).
- Referencias de buenas prácticas: OWASP ASVS (nivel 2 como objetivo) y OWASP Top 10 para aplicaciones con modelos de lenguaje.
- Prueba de intrusión antes del primer cliente de pago y plan de respuesta a incidentes con responsables y plazos.

**Lista de comprobación antes de integrar un cambio** (la usa la skill `security-privacy-review`)

- [ ] Toda consulta nueva filtra por organización.
- [ ] Ningún dato personal ni CUPS completo en logs o mensajes de error.
- [ ] Cualquier texto que salga al proveedor de IA pasa por la pasarela.
- [ ] Los ficheros subidos se validan y se procesan aislados.
- [ ] Sin secretos en el código ni en los datos de prueba.
- [ ] Dependencias analizadas y sin vulnerabilidades críticas conocidas.
- [ ] Pruebas de aislamiento entre clientes en verde.

## 13. Aspectos legales y de cumplimiento

Lo más urgente son tres cosas antes del primer cliente: un contrato de encargo de tratamiento de datos, una autorización firmada para usar los datos del contador y un texto de servicio que no prometa ahorros.

Esta sección es una guía de trabajo, no asesoramiento jurídico. Un abogado debe revisarla antes de contactar con clientes reales.

| Área | Qué implica | Acción |
| --- | --- | --- |
| Protección de datos (RGPD y LOPDGDD) | Las facturas y consumos de una empresa pueden ser datos personales si identifican a una persona física (autónomos, sociedades unipersonales, contactos). Conviene tratarlos todos como tales | Contrato de encargo de tratamiento (artículo 28 del RGPD) en el que el cliente es responsable y tú encargado; registro de actividades; política de privacidad; derechos de acceso y supresión; lista de subencargados |
| Uso de datos para mejorar el producto | Si reutilizas datos de clientes para mejorar el sistema, pasas a ser responsable de ese tratamiento | Anonimizar o pedir permiso expreso y limitarlo a lo necesario |
| Proveedores de IA y nube | Son subencargados; puede haber transferencias fuera de la UE | Contrato de encargo con cada uno, región UE, cláusulas contractuales tipo si hubiera transferencia |
| Brechas de seguridad | Obligación de notificar a la autoridad de protección de datos (AEPD) en 72 horas cuando proceda | Plan de respuesta a incidentes (sección 12) |
| Evaluación de impacto | Probablemente no sea obligatoria, pero la decisión debe documentarse | Documento breve con el análisis y la conclusión |
| Autorización para datos del contador | Acceder a los consumos horarios requiere permiso del titular del suministro | Autorización escrita con alcance y caducidad; VERIFICAR las condiciones de acceso de terceros en Datadis y en cada distribuidora |
| Contrato de servicios | Alcance, límites y responsabilidades | Ver las cláusulas mínimas abajo |
| Honorarios por éxito | Cobrar un porcentaje del ahorro exige definir cómo se mide | Definir línea base, método, periodo de medición, ajustes y derecho del cliente a comprobarlo |
| Actividad en el sector eléctrico | Si gestionas el cambio de comercializadora, actúas en nombre del cliente o recibes comisiones de una comercializadora, pueden aplicar obligaciones de registro y transparencia (Ley 24/2013 del Sector Eléctrico y normas de la CNMC) | VERIFICAR con un abogado y con la CNMC. En la v1: informe independiente, sin comisiones de terceros y sin actuar en nombre del cliente |
| Reglamento de IA de la UE (2024/1689) | Probablemente sistema de riesgo bajo; hay deberes de transparencia si un cliente interactúa con un chat | Clasificar el sistema y documentar la conclusión; VERIFICAR el calendario de aplicación |
| Web y comunicaciones | Aviso legal, cookies y publicidad veraz | Cumplir la LSSI-CE y no publicar cifras de ahorro sin respaldo |
| Fuentes de datos públicas | Cada fuente tiene condiciones de uso | Revisar y citar en el producto (Red Eléctrica, BDNS y otras) |
| Empresa y seguros | Hay que decidir qué entidad presta y factura el servicio | Seguro de responsabilidad civil profesional y alta de actividad correspondiente |

**Cláusulas mínimas del contrato de servicios**

- Objeto y alcance: análisis informativo de facturas y consumos, sin gestión de contratos.
- Sin garantía de ahorro y dependencia de la calidad de los datos facilitados.
- Limitación razonable de responsabilidad e importe máximo.
- Propiedad intelectual: el informe es del cliente y la herramienta y la metodología son tuyas.
- Confidencialidad y, si el cliente lo pide, acuerdo de confidencialidad.
- Protección de datos como anexo (encargo de tratamiento), con plazos de conservación y de borrado.
- Honorarios, forma de calcular el ahorro verificado y plazos de pago.
- Duración, resolución, ley aplicable y jurisdicción.

**Conservación y borrado**

Valor propuesto, que debe decidir el abogado: borrar los ficheros originales a los 90 días de entregar el informe, salvo petición del cliente, y borrar todo el expediente a petición suya en un plazo máximo acordado.

**Aviso obligatorio en cada informe**

> Este informe es informativo. Se basa en los datos facilitados por el cliente y en la normativa vigente en la fecha indicada. Las cifras de ahorro son estimaciones, no están garantizadas y dependen de que se mantengan las condiciones de consumo y de precios.

**Lo que el sistema y el equipo no deben hacer**

- Prometer ahorros concretos antes de analizar datos reales.
- Presentarse como comercializadora, asesor regulado o representante del cliente.
- Usar datos de un cliente en el trabajo de otro.
- Guardar o reutilizar facturas sin anonimizar fuera del encargo.

## 14. Plan de desarrollo por fases

Son ocho fases (de la 0 a la 7), y no se pasa a la siguiente hasta cumplir los criterios de aceptación de la anterior; la fase 1 empieza con la tarifa 2.0TD porque es más simple y permite validar con una factura propia.

&#91;embedded content: fases del desarrollo · 8 fases, 1 bifurcación\]

Las fases 2 y 3 pueden avanzar en paralelo porque ambas dependen solo del motor de cálculo; la fase 4 sigue a la 3 y el análisis necesita las fases 2 y 4.

| Fase | Entregable | Criterios de aceptación | Depende de |
| --- | --- | --- | --- |
| 0. Preparación | Repositorio, integración continua, estructura del proyecto, las 8 skills de la sección 10, datos sintéticos y plan legal mínimo | Skills probadas con una tarea real pequeña; CI en verde; contrato de encargo y autorización redactados y revisados | Nada |
| 1. Motor de cálculo | Reglas versionadas y cálculo de 2.0TD, después 3.0TD y 6.1TD | Reproduce las facturas de referencia dentro de la tolerancia (sección 7); cada regla con fuente y vigencia | Fase 0 |
| 2. Datos horarios y precios | Lectores de CSV por distribuidora, normalización, conector de precios con caché | Casos de cambio de hora y huecos cubiertos; precios reproducibles con fecha de captura | Fase 1 |
| 3. Extracción de facturas | Pasarela de IA, enmascarado de datos personales, extracción con esquema y comprobaciones deterministas | Acierto en campos críticos ≥ 98 % sobre 30 facturas; 0 casos de inyección que cambien un dato | Fase 1 |
| 4. Web y revisión | Aplicación web, subida de ficheros aislada y pantalla de revisión de facturas en estado Revisión | Una factura en Revisión se corrige y se valida sin tocar la base de datos a mano; subida de PDF aislada (sección 9) | Fase 3 |
| 5. Análisis | Módulos A a E con método común y sensibilidad | Cada hallazgo con evidencia, intervalo y confianza; ahorro recalculado por el motor | Fases 2 y 4 |
| 6. Informe y endurecimiento | Informe de una página, comprobador de cifras, revisión de seguridad y prueba de intrusión | Todas las cifras del informe existen en los datos; sin hallazgos críticos ni altos abiertos | Fase 5 |
| 7. Piloto y seguimiento | 3 a 5 clientes piloto, comparación con facturas posteriores, descarga desde Datadis | Al menos 3 de 5 pilotos con ahorro estimado positivo y explicado; errores convertidos en casos de prueba | Fase 6 |

**Reglas de trabajo del agente**

1. Cambios pequeños, cada uno con pruebas y con una nota de qué regla o requisito cubre.
2. Pedir los datos que falten en lugar de suponerlos. Un `VERIFICAR` sin resolver bloquea la fase.
3. Antes de tocar reglas, impuestos o periodos, cargar la skill `es-electricity-tariffs`.
4. Antes de integrar un cambio que toque datos, ficheros o IA, pasar la lista de la sección 12.
5. Un cambio que modifique el resultado de una factura de referencia se explica por escrito y lo aprueba el operador.
6. Registrar decisiones importantes en un fichero de decisiones del repositorio.

## 15. Riesgos, supuestos y preguntas abiertas

El mayor riesgo es el error regulatorio en el cálculo, que se mitiga con reglas versionadas, fuentes citadas y pruebas con facturas reales.

| Riesgo | Mitigación |
| --- | --- |
| Error en una regla, un periodo o un impuesto | Reglas con fuente y vigencia, segunda implementación independiente para comparar, facturas de referencia, revisión humana en los pilotos |
| Extracción incorrecta por un formato nuevo | Validaciones deterministas, revisión humana, nuevos casos de prueba tras cada error |
| Fuga o mal uso de datos de clientes | Controles de la sección 12 y contratos de la sección 13 |
| Ahorro menor al esperado | Intervalos y sensibilidad, expectativas claras, cobrar por ahorro verificado |
| Responsabilidad por una recomendación errónea | Informe informativo, límites contractuales, seguro de responsabilidad civil y confirmación de límites del cliente |
| Dependencia de un proveedor de IA | Pasarela intercambiable y pruebas de evaluación para comparar modelos |
| Cambios en Datadis, en formatos de distribuidoras o en las APIs de precios | Lectores aislados por formato, alertas y datos manuales como alternativa |
| Competencia de asesorías energéticas ya establecidas | Foco en un sector, rapidez y análisis de datos horarios con informe verificable |

**Supuestos**

- Los clientes aceptan compartir facturas y datos horarios con una autorización firmada.
- Se puede obtener el consumo horario de la distribuidora de cada cliente.
- Los ahorros por potencia, reactiva y modalidad de precio son suficientes para justificar el servicio en plantas agroalimentarias.

**Preguntas abiertas**

- [ ] ¿Se empieza el piloto con 3.0TD o con 6.1TD?
- [ ] ¿Qué proveedor de IA y qué proveedor de alojamiento se usan, y en qué región?
- [ ] ¿Qué entidad presta el servicio y factura?
- [ ] ¿Cuál es el modelo de honorarios para el piloto (gratuito, fijo o por ahorro verificado)?
- [ ] ¿Qué plazo de conservación de datos se acuerda con los clientes?
- [ ] ¿Quién revisa los contratos y la parte regulatoria?

## Fuentes

Son resultados de búsqueda consultados al preparar este documento, no normativa. El agente debe verificar cada dato en la fuente oficial (BOE, CNMC, Ministerio) antes de usarlo.

- [CNMC, nueva estructura de la factura de la luz (2.0TD)](https://www.cnmc.es/file/304115/download)
- [CNMC, componentes de la factura](https://cnmc.es/file/305274/download)
- [Revista Negocios, precio de la luz para pymes (IVA e impuesto eléctrico en 2026)](https://revistanegocios.es/precio-luz-pymes-espanolas-abril-2026/)
- [SotySolar, subida de la luz en 2026 (IVA)](https://sotysolar.es/blog/luz-subida-precio-espana)
- [Red Eléctrica, API REData](https://www.ree.es/en/datos/apidata)
- [Luzfija, consumo horario y Datadis](https://luzfija.es/guias/como-ver-tu-consumo-horario-real-el-del-contador-no-el-estimado.html)
- [Nergiza, formatos de CSV de distribuidoras y simulador de la CNMC](https://nergiza.com/como-utilizar-el-simulador-de-la-cnmc-para-reducir-tu-factura-de-la-luz/)
- [Enertra, ahorro energético en empresas](https://enertra.es/ahorro-energetico-empresas/)
