"""Comprobaciones deterministas de un documento: las hace el código, sin la IA y sin tolerancia (al céntimo).

Cada incumplimiento es información para el humano que revisa; nunca corrige un dato por su cuenta.
"""

from dataclasses import dataclass
from decimal import Decimal

from .models import Documento
from .numeros import eur, num, redondear


@dataclass(frozen=True)
class Comprobacion:
    campo: str
    texto: str


def comprobar(doc: Documento) -> list[Comprobacion]:
    fallos: list[Comprobacion] = []
    lineas = list(doc.lineas.all())
    iva = list(doc.desglose_iva.all())

    for campo, etiqueta in (
        ("numero", "el número del documento"),
        ("fecha", "la fecha"),
        ("proveedor_nombre", "el nombre del proveedor"),
    ):
        if not getattr(doc, campo):
            fallos.append(Comprobacion(campo, f"Falta {etiqueta}."))

    importes = [li.importe for li in lineas if li.importe is not None]
    if importes and doc.base_imponible is not None:
        suma = sum(importes, Decimal(0))
        if suma != doc.base_imponible:
            fallos.append(
                Comprobacion(
                    "base_imponible", f"Las líneas suman {eur(suma)} y la base imponible es {eur(doc.base_imponible)}."
                )
            )

    bases = [d.base for d in iva if d.base is not None]
    if bases and doc.base_imponible is not None and sum(bases, Decimal(0)) != doc.base_imponible:
        fallos.append(
            Comprobacion(
                "iva",
                f"Las bases del IVA suman {eur(sum(bases, Decimal(0)))} y la base imponible "
                f"es {eur(doc.base_imponible)}.",
            )
        )

    for d in iva:
        if d.base is not None and d.cuota is not None:
            esperada = redondear(d.base * d.tipo / 100)
            if esperada != d.cuota:
                fallos.append(
                    Comprobacion(
                        "iva",
                        f"El IVA del {num(d.tipo, 0)} % sobre {eur(d.base)} sería "
                        f"{eur(esperada)} y el documento pone {eur(d.cuota)}.",
                    )
                )

    cuotas = [d.cuota for d in iva if d.cuota is not None]
    if doc.base_imponible is not None and doc.total is not None and cuotas:
        esperado = doc.base_imponible + sum(cuotas, Decimal(0))
        if esperado != doc.total:
            fallos.append(Comprobacion("total", f"Base más IVA suman {eur(esperado)} y el total es {eur(doc.total)}."))

    for n, li in enumerate(lineas, start=1):
        if li.cantidad is not None and li.precio_unitario is not None and li.importe is not None and not li.descuento:
            esperado = redondear(li.cantidad * li.precio_unitario)
            if esperado != li.importe:
                fallos.append(
                    Comprobacion(
                        "lineas",
                        f"Línea {n}: {num(li.cantidad, 3)} × {num(li.precio_unitario, 2)} "
                        f"son {eur(esperado)} y el importe es {eur(li.importe)}.",
                    )
                )
    return fallos
