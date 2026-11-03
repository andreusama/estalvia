"""Birròmetro: cuánto se gana con un barril. Todo con decimales exactos y calculado aquí, nunca por la IA.

Un barril de `litros` cuesta `precio` (sin IVA). Se pierde una `merma` en espuma y derrames y el resto se sirve en
raciones enteras de `servicio_cl`; cada una se cobra a `precio_venta` con IVA. El beneficio compara lo que entra sin
IVA con lo que costó el barril (no cuenta alquiler, personal ni luz).
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .numeros import redondear

CIEN = Decimal(100)
UMBRAL_SUBIDA = Decimal("5")  # % de subida del coste por litro que se avisa (el mismo 5 % por defecto de las alertas)
SERVICIOS = [
    (20, "Caña (20 cl)"),
    (25, "Caña grande (25 cl)"),
    (33, "Tercio (33 cl)"),
    (40, "Jarra (40 cl)"),
    (50, "Pinta (50 cl)"),
]
IVAS = [(10, "10 % (hostelería)"), (21, "21 %")]


@dataclass(frozen=True)
class Resultado:
    servicios: int  # raciones enteras que salen del barril
    litros_perdidos: Decimal
    coste_litro: Decimal
    coste_servicio: Decimal | None
    venta_neta_servicio: Decimal | None  # lo que entra por ración, sin IVA
    beneficio_servicio: Decimal | None
    ingresos_netos: Decimal
    beneficio: Decimal
    margen: Decimal | None  # % del beneficio sobre lo que entra sin IVA
    precio_minimo: Decimal | None  # el precio (con IVA) por debajo del cual se pierde dinero

    @property
    def gana(self) -> bool:
        return self.beneficio >= 0


def calcular(
    litros: Decimal, precio: Decimal, precio_venta: Decimal, servicio_cl: int, merma: Decimal, iva: Decimal
) -> Resultado:
    litros_utiles = litros * (CIEN - merma) / CIEN
    servicios = int((litros_utiles * CIEN / Decimal(servicio_cl)).to_integral_value(rounding=ROUND_FLOOR))
    factor_iva = 1 + iva / CIEN
    ingresos = redondear(Decimal(servicios) * precio_venta / factor_iva)
    beneficio = redondear(ingresos - precio)
    n = Decimal(servicios)
    return Resultado(
        servicios=servicios,
        litros_perdidos=litros - litros_utiles,
        coste_litro=redondear(precio / litros),
        coste_servicio=redondear(precio / n) if servicios else None,
        venta_neta_servicio=redondear(ingresos / n) if servicios else None,
        beneficio_servicio=redondear(beneficio / n) if servicios else None,
        ingresos_netos=ingresos,
        beneficio=beneficio,
        margen=(beneficio / ingresos * CIEN).quantize(Decimal("0.1")) if ingresos else None,
        precio_minimo=(precio * factor_iva / n).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        if servicios
        else None,
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
