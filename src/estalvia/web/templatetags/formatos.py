from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()


def _es(valor: Decimal, decimales: int) -> str:
    q = valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    entero, _, frac = f"{q:f}".partition(".")
    signo = "-" if entero.startswith("-") and q != 0 else ""
    entero = entero.lstrip("-")
    miles = f"{int(entero):,}".replace(",", ".")
    return f"{signo}{miles}" + (f",{frac}" if decimales else "")


@register.filter
def eur(valor: Decimal) -> str:
    return _es(valor, 2) + " €"


@register.filter
def numero(valor: Decimal) -> str:
    """Cantidad sin ceros de más (4 kWh, no 4,00); hasta 3 decimales."""
    q = valor.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP).normalize()
    dec = max(0, -q.as_tuple().exponent)
    return _es(q.quantize(Decimal(1).scaleb(-dec)), dec)


@register.filter
def fecha(valor) -> str:
    return valor.strftime("%d/%m/%Y")


@register.filter
def kwh(valor: Decimal) -> str:
    """kWh para leer de un vistazo: un decimal desde 10 kWh, dos por debajo (0,97 no puede quedar en 1,0)."""
    return _es(valor, 1 if abs(valor) >= 10 else 2)
