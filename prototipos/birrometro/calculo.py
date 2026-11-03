"""Birròmetro: cuánto se gana con un barril. Todo con decimales exactos y calculado aquí, nunca por la IA.

Un barril de `litros` cuesta `precio` (sin IVA). Se pierde una `merma` en espuma y derrames y el resto se reparte en
las raciones que decides sacar (zurritos, cañas, jarras...), sin pasarte de los litros que quedan. Cada ración se cobra
con IVA. El beneficio compara lo que entra sin IVA con lo que costó el barril entero (no cuenta alquiler, personal ni
luz); lo que no se sirve se pierde y se nota en el beneficio.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .numeros import redondear

CIEN = Decimal(100)
UMBRAL_SUBIDA = Decimal("5")  # % de subida del coste por litro que se avisa (el mismo 5 % por defecto de las alertas)
IVAS = [(10, "10 % (hostelería)"), (21, "21 %")]
# Los tres tipos de ración: clave, nombre, centilitros y precio de partida. Tamaño y precio se cambian en la pantalla.
TIPOS = [
    ("zurrito", "Zurrito", 15, "1.80"),
    ("cana", "Caña", 20, "2.50"),
    ("jarra", "Jarra", 40, "4.00"),
]


@dataclass(frozen=True)
class Racion:
    nombre: str
    cl: int
    precio_venta: Decimal  # con IVA
    cantidad: int


@dataclass(frozen=True)
class LineaRacion:
    racion: Racion
    maximo: int  # las que cabrían si todo el barril fuera de este tipo
    coste: Decimal  # lo que cuesta cada una (el barril repartido entre los litros que se pueden servir)
    venta_neta: Decimal  # lo que entra por cada una, sin IVA
    beneficio: Decimal  # lo que ganas por cada una
    precio_minimo: Decimal  # precio con IVA por debajo del cual se pierde en cada una
    ingresos: Decimal  # lo que entra con todas las que sacas, sin IVA


@dataclass(frozen=True)
class Resultado:
    lineas: list[LineaRacion]
    litros_utiles: Decimal
    litros_perdidos: Decimal  # merma
    litros_servidos: Decimal
    litros_sobran: Decimal  # servibles que no has repartido
    coste_litro: Decimal
    ingresos_netos: Decimal
    beneficio: Decimal
    margen: Decimal | None  # % del beneficio sobre lo que entra sin IVA

    @property
    def gana(self) -> bool:
        return self.beneficio >= 0

    @property
    def sirve_algo(self) -> bool:
        return any(linea.racion.cantidad for linea in self.lineas)


def litros_utiles(litros: Decimal, merma: Decimal) -> Decimal:
    return litros * (CIEN - merma) / CIEN


def litros_de(raciones: list[Racion]) -> Decimal:
    return sum((Decimal(r.cantidad * r.cl) / CIEN for r in raciones), Decimal(0))


def calcular(litros: Decimal, precio: Decimal, raciones: list[Racion], merma: Decimal, iva: Decimal) -> Resultado:
    """Reparte el barril. Quien llama ya ha comprobado que las raciones caben (`litros_de` ≤ `litros_utiles`)."""
    utiles = litros_utiles(litros, merma)
    factor_iva = 1 + iva / CIEN
    coste_por_litro_util = precio / utiles
    lineas, ingresos = [], Decimal(0)
    for r in raciones:
        coste = coste_por_litro_util * r.cl / CIEN
        venta_neta = r.precio_venta / factor_iva
        total = Decimal(r.cantidad) * venta_neta
        ingresos += total
        lineas.append(
            LineaRacion(
                racion=r,
                maximo=int((utiles * CIEN / Decimal(r.cl)).to_integral_value(rounding=ROUND_FLOOR)),
                coste=redondear(coste),
                venta_neta=redondear(venta_neta),
                beneficio=redondear(venta_neta - coste),
                precio_minimo=(coste * factor_iva).quantize(Decimal("0.01"), rounding=ROUND_CEILING),
                ingresos=redondear(total),
            )
        )
    ingresos = redondear(ingresos)
    beneficio = redondear(ingresos - precio)
    servidos = litros_de(raciones)
    return Resultado(
        lineas=lineas,
        litros_utiles=utiles,
        litros_perdidos=litros - utiles,
        litros_servidos=servidos,
        litros_sobran=utiles - servidos,
        coste_litro=redondear(precio / litros),
        ingresos_netos=ingresos,
        beneficio=beneficio,
        margen=(beneficio / ingresos * CIEN).quantize(Decimal("0.1")) if ingresos else None,
    )


def cambio_de_precio(coste_litro: Decimal, anterior: Decimal | None) -> Decimal | None:
    """% que ha subido (o bajado, negativo) el coste por litro respecto al barril anterior de la marca."""
    if not anterior:
        return None
    return ((coste_litro - anterior) / anterior * CIEN).quantize(Decimal("0.1"))


def anterior_de_la_marca(barriles, marca: str, fecha: date, excluir_pk=None):
    """El último barril de esa marca comprado antes que `fecha`."""
    clave = marca.strip().casefold()
    for b in barriles:  # ya vienen del más reciente al más antiguo
        if (excluir_pk is None or b.pk != excluir_pk) and b.marca.strip().casefold() == clave and b.fecha < fecha:
            return b
    return None
