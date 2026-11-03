"""Lectura de importes y formato español. Aquí no se calcula nada: solo se convierte texto en Decimal y viceversa."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.utils import formats

CENTIMO = Decimal("0.01")


def a_decimal(valor) -> Decimal | None:
    """Acepta `10.49`, `10,49`, `1.248,60`, `1,248.60` y `12,69 €`. Lo ilegible devuelve None."""
    if valor is None:
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    s = str(valor).replace("€", "").replace(" ", "").replace(" ", "").strip()
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def ajustar(valor: Decimal | None, digitos: int, decimales: int) -> Decimal | None:
    """Encaja el valor en la columna de la base de datos; si no cabe, None (y el campo se marca dudoso aparte)."""
    if valor is None:
        return None
    d = valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    return d if abs(d) < Decimal(10) ** (digitos - decimales) else None


def redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTIMO, rounding=ROUND_HALF_UP)


def eur(valor: Decimal | None) -> str:
    if valor is None:
        return "—"
    return formats.number_format(redondear(valor), decimal_pos=2, force_grouping=True) + " €"


def num(valor: Decimal | None, decimales: int = 2) -> str:
    if valor is None:
        return ""
    return formats.number_format(valor, decimal_pos=decimales, force_grouping=True)


def normalizar_referencia(texto: str) -> str:
    """A.28541, A-28541 y a 28541 son la misma referencia."""
    return "".join(c for c in texto.upper() if c.isalnum())
