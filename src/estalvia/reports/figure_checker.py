"""Comprobador de cifras: toda cifra del texto generado debe existir en los datos (TDD sección 9)."""
import re
from decimal import Decimal

NUM = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _parse(s: str) -> Decimal:
    return Decimal(s.replace(".", "").replace(",", "."))


def cifras_del_texto(texto: str) -> list[Decimal]:
    return [_parse(m) for m in NUM.findall(texto)]


def cifras_inexistentes(texto: str, datos: set[Decimal]) -> list[Decimal]:
    return [c for c in cifras_del_texto(texto) if c not in datos]
