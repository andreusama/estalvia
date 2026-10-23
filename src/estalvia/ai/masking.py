"""Enmascarado previo al envío de texto al proveedor de IA (TDD sección 9, límite 7).

Primera versión por patrones; los nombres y direcciones requieren el contexto de la factura
y se pasan como `extra` por el llamante.
"""
import re

NIF = re.compile(r"\b(?:[XYZ]\d{7}[A-Z]|\d{8}[A-Z]|[A-HJNPQRSUVW]\d{7}[0-9A-J])\b")
CUPS = re.compile(r"\bES\d{16}[A-Z]{2}(?:\d[A-Z])?\b", re.IGNORECASE)
IBAN = re.compile(r"\bES\d{2}(?:\s?\d{4}){5}\b")


def enmascarar(texto: str, extra: list[str] | None = None) -> str:
    texto = NIF.sub("[NIF]", texto)
    texto = CUPS.sub(lambda m: m.group(0)[:4] + "…[CUPS]", texto)
    texto = IBAN.sub("[IBAN]", texto)
    for s in extra or []:
        if s.strip():
            texto = re.sub(re.escape(s), "[DATO]", texto, flags=re.IGNORECASE)
    return texto
