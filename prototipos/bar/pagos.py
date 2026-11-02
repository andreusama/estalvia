"""Proponer qué movimiento del banco paga qué factura, y explicar todo lo que no encaja.

Reglas en código, con decimales exactos y sin tolerancia: solo un importe idéntico se propone para confirmar. Lo
parecido se enseña como pista con su explicación, nunca como pago. Propone poco y lo explica todo; confirma una persona.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .models import Documento, Movimiento, Pago
from .numeros import eur, normalizar_referencia

UMBRAL_PARECIDO = Decimal(
    "0.10"
)  # un pago hasta un 10 % distinto de una factura del mismo proveedor se enseña como pista
MIN_REFERENCIA = 4  # una referencia de menos de 4 caracteres coincidiría con cualquier cosa
FORMAS_JURIDICAS = {"SL", "SA", "SLU", "SLL", "SAU", "SC", "CB", "SCP", "SRL", "LTD", "GMBH"}

# Tipos de veredicto
EXACTO, DOBLE, DISTINTO, SIN_FACTURA, DEVOLUCION, PISTA = (
    "exacto", "doble", "distinto", "sin_factura", "devolucion", "pista"
)  # fmt: skip


@dataclass(frozen=True)
class Veredicto:
    movimiento: Movimiento
    tipo: str
    texto: str
    factura: Documento | None = None
    proveedor: str = ""

    @property
    def confirmable(self) -> bool:
        return self.tipo == EXACTO

    @property
    def etiqueta(self) -> str:
        return ETIQUETAS[self.tipo]

    @property
    def estilo(self) -> str:
        """Color con significado: gris = informa, rojo = hay que mirarlo, verde = coincide."""
        return {EXACTO: "ok", DEVOLUCION: "wait", PISTA: "wait"}.get(self.tipo, "diff")

    @property
    def simbolo(self) -> str:
        return {EXACTO: "=", DEVOLUCION: "?", PISTA: "?"}.get(self.tipo, "≠")


ETIQUETAS = {
    EXACTO: "Pago exacto",
    DOBLE: "Posible cobro doble",
    DISTINTO: "Importe distinto",
    SIN_FACTURA: "Pago sin factura",
    DEVOLUCION: "Entra dinero",
    PISTA: "Mismo importe, otro concepto",
}


def _limpiar(texto: str) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", " ", sin_acentos.upper()).strip()


def _palabras_proveedor(nombre: str) -> list[str]:
    return [p for p in _limpiar(nombre).split() if len(p) >= 3 and p not in FORMAS_JURIDICAS]


def proveedor_en(concepto: str, nombres: list[str]) -> str:
    """El proveedor cuyo nombre (todas sus palabras importantes) aparece en el concepto del movimiento."""
    palabras_concepto = set(_limpiar(concepto).split())
    for nombre in nombres:
        palabras = _palabras_proveedor(nombre)
        if palabras and all(p in palabras_concepto for p in palabras):
            return nombre
    return ""


def referencia_en(numero: str, concepto: str) -> bool:
    ref = normalizar_referencia(numero)
    return len(ref) >= MIN_REFERENCIA and ref in normalizar_referencia(concepto)


def factura_citada(concepto: str) -> str:
    """«FRA F26-24410» → F26-24410: la referencia que cita el concepto, aunque la factura no esté subida."""
    m = re.search(r"\b(?:FRA|FACT|FACTURA)\.?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/.]{2,})", concepto.upper())
    return m.group(1).rstrip(".") if m else ""


def pagado(factura: Documento) -> Decimal:
    return factura.pagos.aggregate(t=Sum("importe"))["t"] or Decimal("0.00")


def esta_pagada(factura: Documento) -> bool:
    return factura.total is not None and pagado(factura) >= factura.total


def facturas() -> list[Documento]:
    """Facturas leídas (revisadas o no), con sus pagos. Las no revisadas se tratan como provisionales."""
    docs = Documento.objects.filter(
        tipo=Documento.Tipo.FACTURA, estado__in=[Documento.Estado.PROCESADO, Documento.Estado.REVISADO]
    ).defer("archivo", "respuesta_ia")
    docs = list(docs.prefetch_related("pagos").order_by("fecha", "id"))
    for d in docs:
        d.pagado = sum((p.importe for p in d.pagos.all()), Decimal("0.00"))
        d.pendiente = (d.total - d.pagado) if d.total is not None else None
        d.esta_pagada = d.total is not None and d.pagado >= d.total
    return docs


def movimientos_por_mirar() -> list[Movimiento]:
    """Movimientos que aún no son un pago confirmado ni se han marcado como vistos."""
    return list(Movimiento.objects.filter(pago__isnull=True, ignorado_en__isnull=True).order_by("fecha", "id"))


def analizar(movimientos: list[Movimiento], todas: list[Documento]) -> list[Veredicto]:
    """Un veredicto por cada movimiento relacionado con un proveedor; el resto (ventas, luz, alquiler) se ignora."""
    nombres = sorted({d.proveedor_nombre for d in todas if d.proveedor_nombre})
    reclamadas: set[int] = set()  # facturas ya propuestas a un movimiento anterior
    pago_de: dict[int, Movimiento] = {}
    for d in todas:
        for p in d.pagos.all():
            if p.movimiento_id:
                pago_de[d.pk] = p.movimiento
    veredictos: list[Veredicto] = []

    def parecido(a: Decimal, b: Decimal) -> bool:
        return b != 0 and abs(a - b) / b <= UMBRAL_PARECIDO

    for m in movimientos:
        gasto = -m.importe
        prov = proveedor_en(m.concepto, nombres)

        if m.importe > 0:
            if prov:
                veredictos.append(
                    Veredicto(
                        m,
                        DEVOLUCION,
                        f"Entran {eur(m.importe)} de {prov}: posible abono o devolución. Solo es un aviso.",
                        proveedor=prov,
                    )
                )
            continue

        con_referencia = [d for d in todas if d.numero and d.total is not None and referencia_en(d.numero, m.concepto)]
        exactas = [d for d in con_referencia if d.total == gasto]
        if exactas:
            f = exactas[0]
            if f.esta_pagada or f.pk in reclamadas:
                antes = pago_de.get(f.pk)
                ya = f"ya tiene un pago del {antes.fecha:%d/%m}" if antes else "ya está propuesta para otro movimiento"
                veredictos.append(
                    Veredicto(
                        m, DOBLE,
                        f"La factura {f.numero} ({f.proveedor_nombre}) {ya} por {eur(f.total)}. "
                        "Este podría ser un cobro doble: comprueba con el banco.",
                        f, f.proveedor_nombre,
                    )
                )  # fmt: skip
            else:
                reclamadas.add(f.pk)
                veredictos.append(
                    Veredicto(
                        m, EXACTO,
                        f"El concepto cita la factura {f.numero} y el importe coincide al céntimo ({eur(f.total)}).",
                        f, f.proveedor_nombre,
                    )
                )  # fmt: skip
            continue
        if con_referencia:
            f = con_referencia[0]
            dif = gasto - f.total
            veredictos.append(
                Veredicto(
                    m, DISTINTO,
                    f"El concepto cita la factura {f.numero}, que es de {eur(f.total)}; el banco cobra {eur(gasto)} "
                    f"({'+' if dif > 0 else '−'}{eur(abs(dif))}). No se da por pagada.",
                    f, f.proveedor_nombre,
                )
            )  # fmt: skip
            continue

        iguales = [d for d in todas if d.total == gasto and not d.esta_pagada and d.pk not in reclamadas]
        del_proveedor = [d for d in iguales if prov and d.proveedor_nombre == prov]
        if del_proveedor:
            f = del_proveedor[0]
            reclamadas.add(f.pk)
            veredictos.append(
                Veredicto(
                    m, EXACTO,
                    f"{prov} figura en el concepto y el importe coincide al céntimo con la factura {f.numero} "
                    f"({eur(f.total)}). El concepto no cita el número de factura.",
                    f, prov,
                )
            )  # fmt: skip
            continue
        if iguales and not prov:
            f = iguales[0]
            veredictos.append(
                Veredicto(
                    m, PISTA,
                    f"Mismo importe que la factura {f.numero} de {f.proveedor_nombre} ({eur(f.total)}), pero el "
                    "concepto no nombra al proveedor. No se propone como pago.",
                    f, f.proveedor_nombre,
                )
            )  # fmt: skip
            continue
        if prov:
            suyas = [d for d in todas if d.proveedor_nombre == prov and d.total is not None]
            cerca = [d for d in suyas if parecido(gasto, d.total)]
            if cerca:
                f = min(cerca, key=lambda d: abs(gasto - d.total))
                dif = gasto - f.total
                estado = "ya está pagada" if f.esta_pagada else "sigue pendiente"
                veredictos.append(
                    Veredicto(
                        m, DISTINTO,
                        f"Pago a {prov} de {eur(gasto)}, parecido a la factura {f.numero} ({eur(f.total)}, "
                        f"{'+' if dif > 0 else '−'}{eur(abs(dif))}), que {estado}. No se da por pagada ninguna.",
                        f, prov,
                    )
                )  # fmt: skip
            else:
                citada = factura_citada(m.concepto)
                cita = f" Cita la factura {citada}, que no está subida." if citada else ""
                veredictos.append(
                    Veredicto(
                        m, SIN_FACTURA,
                        f"Pago de {eur(gasto)} a {prov} sin ninguna factura que lo explique.{cita} Sube la factura.",
                        proveedor=prov,
                    )
                )  # fmt: skip
    return veredictos


def confirmar_pago(movimiento: Movimiento, factura: Documento) -> Pago:
    """Registra el pago. Quien llama ya ha comprobado que el veredicto es EXACTO."""
    from . import servicios

    pago = Pago.objects.create(
        documento=factura, movimiento=movimiento, importe=-movimiento.importe, metodo=Pago.Metodo.BANCO
    )
    servicios.registrar(
        factura, "pagado", f"Pago confirmado: movimiento del {movimiento.fecha:%d/%m/%Y} por {eur(-movimiento.importe)}"
    )
    return pago


def pagar_en_efectivo(factura: Documento) -> Pago:
    from . import servicios

    resto = factura.total - pagado(factura)
    pago = Pago.objects.create(documento=factura, importe=resto, metodo=Pago.Metodo.EFECTIVO)
    servicios.registrar(factura, "pagado", f"Marcada como pagada en efectivo por {eur(resto)}")
    return pago


def vencida(factura: Documento, hoy: date) -> bool:
    return bool(factura.vencimiento and factura.vencimiento < hoy and not factura.esta_pagada)
