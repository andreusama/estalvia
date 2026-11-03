# Bar

Herramienta de información para el dueño de un bar: a partir de fotos de albaranes, facturas y tickets de sus proveedores, muestra qué le cobran, qué ha pagado, qué está pendiente y qué no cuadra. No decide nada por él: informa y explica.

## Language

### Documentos

**Documento**:
Un archivo subido (foto o PDF) que es un albarán, una factura o un ticket. Un archivo es un solo documento.
_Avoid_: archivo (a secas), registro, papel

**Albarán**:
Documento que acompaña a una entrega e indica lo recibido, sin ser una petición de pago.
_Avoid_: nota de entrega, delivery note

**Factura**:
Documento con el que un proveedor pide el pago, y puede agrupar varios albaranes.
_Avoid_: bill, recibo

**Ticket**:
Comprobante de una compra pagada en el momento. Cuenta como gasto y nace pagado.
_Avoid_: recibo, comprobante

**Proveedor**:
Quien vende al bar, identificado por nombre y, si aparece, NIF.
_Avoid_: vendedor, empresa

**Línea**:
Un producto de un documento con su cantidad, unidad, precio unitario e importe, tal como lo imprime el proveedor.
_Avoid_: item, renglón

### Productos y precios

**Producto**:
Lo que el bar compra, con un nombre propio y una unidad base, sea cual sea cómo lo llame cada proveedor.
_Avoid_: artículo, referencia

**Alias**:
El nombre con que un proveedor concreto llama a un producto. Una línea sin alias conocido queda sin asignar hasta que un humano la asigna.
_Avoid_: sinónimo, apodo

**Subida de precio**:
Aumento del precio unitario de un producto respecto a la compra anterior al mismo proveedor y en la misma unidad. Solo existe si las unidades coinciden.
_Avoid_: inflación, variación

### Revisión y confianza

**Lectura**:
Paso en que la IA transcribe un documento: copia lo impreso, no calcula nada y deja en blanco o marca como dudoso lo que no ve con seguridad.
_Avoid_: extracción, OCR, análisis

**Comprobación**:
Regla escrita en código que valida las cifras de un documento sin intervención de la IA y sin tolerancia: las líneas suman la base, base más IVA es el total.
_Avoid_: validación, verificación

**Revisado**:
Estado de un documento cuyos datos ha comprobado y corregido un humano. Ninguna cifra se da por buena sin pasar por aquí.
_Avoid_: validado, aprobado

**Provisional**:
Etiqueta de toda cifra o alerta que depende de algún documento sin revisar.
_Avoid_: estimado, borrador

**Dudoso**:
Campo que la IA marca como poco seguro, o documento cuyas cifras no cuadran exactamente, sin tolerancia: las líneas deben sumar la base, y base más IVA debe ser el total.
_Avoid_: error, sospechoso

### Conciliación

**Conciliación**:
Emparejar una factura con los albaranes que cubre y señalar lo que no encaja.
_Avoid_: cruce, matching

**Albarán sin factura**:
Albarán entregado del que no consta factura, salvo que se haya marcado «sin factura esperada» (por ejemplo, pagado en efectivo en la entrega).
_Avoid_: albarán huérfano

**Factura sin albarán**:
Factura que no enlaza con ningún albarán.
_Avoid_: factura huérfana

**Duplicado posible**:
Dos documentos del mismo proveedor y tipo con el mismo número, o con el mismo total exacto y fechas a menos de 7 días. Se avisa y se muestran juntos; solo un humano decide.
_Avoid_: duplicado (a secas), repetido

**Discrepancia**:
Cualquier diferencia entre lo que dicen los albaranes y lo que cobra la factura que los cubre: precio, cantidad, línea que falta o línea que sobra.
_Avoid_: diferencia, descuadre

**Ventana de emparejado**:
Días máximos antes de una factura en los que se buscan albaranes sin referencia para proponerlos. Configurable.
_Avoid_: margen de fechas

### Pagos

**Movimiento**:
Una línea del extracto bancario importado.
_Avoid_: apunte, transacción

**Pago**:
El hecho de que una factura está pagada, por un movimiento bancario confirmado o marcada a mano como pagada en efectivo.
_Avoid_: cobro, abono

**Pendiente**:
Factura sin pago confirmado.
_Avoid_: impagada, por pagar

**Perfil del banco**:
Cómo se lee el extracto de un banco: separador, formato de fecha y de números y nombre de cada columna. Sin claves ni número de cuenta completo.
_Avoid_: plantilla, configuración

**Pago propuesto**:
Movimiento cuyo importe coincide al céntimo con una factura y que una persona puede confirmar. Lo parecido nunca se propone: se enseña como pista.
_Avoid_: pago automático, emparejado

**Cobro doble**:
Segundo movimiento idéntico para una factura que ya tiene pago o ya está propuesta a otro movimiento. Solo se avisa.
_Avoid_: duplicado de pago
