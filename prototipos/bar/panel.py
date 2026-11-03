"""Cifras reales del Bar para Resumen, Revisar y el contador rojo de la barra inferior."""

from decimal import Decimal

from . import pagos as banco
from .comprobaciones import comprobar
from .models import Documento


def documentos_por_revisar(usuario) -> list[Documento]:
    """Documentos que esperan a una persona o no se pudieron leer; primero los que no cuadran, luego por importe."""
    docs = list(
        Documento.objects.filter(propietario=usuario, estado__in=[Documento.Estado.PROCESADO, Documento.Estado.ERROR])
        .defer("archivo", "respuesta_ia")
        .prefetch_related("lineas", "desglose_iva")
    )
    for d in docs:
        d.fallos = comprobar(d) if d.estado == Documento.Estado.PROCESADO else []
    docs.sort(key=lambda d: (not d.fallos, -(d.total or Decimal(0))))
    return docs


def cifras(usuario) -> dict:
    """Todo sale de documentos y movimientos reales. El contador cuenta lo que requiere una acción tuya."""
    docs = documentos_por_revisar(usuario)
    facturas = banco.facturas(usuario)
    veredictos = banco.analizar(banco.movimientos_por_mirar(usuario), facturas)
    avisos = [v for v in veredictos if v.estilo == "diff"]  # cobro doble, importe distinto, pago sin factura
    return {
        "docs": docs,
        "veredictos": veredictos,
        "avisos": avisos,
        "por_confirmar": sum(1 for v in veredictos if v.confirmable),
        "pagadas": sum(1 for f in facturas if f.esta_pagada),
        "sin_pagar": sum(1 for f in facturas if not f.esta_pagada and f.total is not None),
        "por_revisar": len(docs),
        "contador": len(docs) + len(avisos),
    }
