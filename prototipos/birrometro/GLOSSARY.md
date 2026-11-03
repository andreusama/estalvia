# Birròmetro

Calcula cuánto se gana con un barril de cerveza según cuántas raciones se sacan de cada tipo. Es una herramienta aparte del Bar: no comparte pantallas ni datos con los albaranes.

## Language

**Barril**: la compra de un barril de una marca: litros, fecha y precio sin IVA.
_Evitar_: pedido, factura

**Ración**: un tipo de servicio que se saca del barril (zurrito, caña o jarra), con su tamaño en centilitros, su precio de venta con IVA y cuántas se sacan.

**Merma**: el porcentaje del barril que se pierde en espuma, derrames y el final del barril.

**Litros servibles**: los litros del barril menos la merma. Las raciones que se sacan no pueden pasarse de ellos.

**Sin repartir**: los litros servibles que no se asignan a ninguna ración. Se pierden, pero el barril se paga entero.

**Beneficio**: lo que entra por las raciones sin IVA menos lo que costó el barril. No cuenta personal, alquiler ni luz.

**Precio mínimo**: el precio con IVA de una ración por debajo del cual se pierde dinero con esa ración.

**Subida de precio**: el coste por litro de un barril comparado con el barril anterior de la misma marca; se avisa a partir del 5 %.
