"""Estado de cada grupo albarán-factura. Lo decide el código, no la IA, y sin tolerancia: o coincide al céntimo o no."""

from dataclasses import dataclass
from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

OK, DIFF, WAIT = "ok", "diff", "wait"


@dataclass(frozen=True)
class Documento:
    tipo: str  # "Albarán" | "Factura"
    numero: str
    importe: Decimal


@dataclass(frozen=True)
class Grupo:
    proveedor: str
    albaran: Documento
    factura: Documento | None
    nota_extra: str = ""  # p. ej. «Entregado el 30 de octubre»

    @property
    def diferencia(self) -> Decimal | None:
        return None if self.factura is None else self.factura.importe - self.albaran.importe

    @property
    def estado(self) -> str:
        if self.factura is None:
            return WAIT
        return OK if self.diferencia == 0 else DIFF

    @property
    def nota(self) -> str:
        if self.estado == OK:
            return str(_("El importe del albarán y el de la factura es el mismo."))
        if self.estado == DIFF:
            d = self.diferencia
            texto = (
                _("La factura cobra %(n)s € de más sobre lo entregado.")
                if d > 0
                else _("La factura cobra %(n)s € de menos sobre lo entregado.")
            )
            return str(texto) % {"n": f"{abs(d):.2f}".replace(".", ",")}
        return (self.nota_extra + " " if self.nota_extra else "") + str(_("Aún no hace falta hacer nada."))


def contar(grupos: list[Grupo]) -> dict[str, int]:
    return {e: sum(g.estado == e for g in grupos) for e in (OK, DIFF, WAIT)}


def secciones(grupos: list[Grupo]) -> list[dict]:
    """Lo que requiere acción primero, luego lo pendiente, y al final lo que coincide. Las secciones vacías no salen."""
    n = contar(grupos)
    titulos = {
        DIFF: (
            _("Requiere tu acción"),
            ngettext("Una diferencia por revisar", "%(n)d diferencias por revisar", n[DIFF]) % {"n": n[DIFF]},
        ),
        WAIT: (_("Pendiente"), ngettext("Esperando una factura", "Esperando %(n)d facturas", n[WAIT]) % {"n": n[WAIT]}),
        OK: (_("Todo en orden"), _("Coinciden")),
    }
    return [
        {"estado": e, "sobre": titulos[e][0], "titulo": titulos[e][1], "grupos": [g for g in grupos if g.estado == e]}
        for e in (DIFF, WAIT, OK)
        if n[e]
    ]
