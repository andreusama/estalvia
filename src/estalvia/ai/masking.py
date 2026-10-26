"""Enmascarado previo al envío de texto al proveedor de IA (TDD sección 9, límite 7; spec #10).

Quita lo que no hace falta para calcular: nombre, dirección, teléfono, correo, NIF, IBAN, números de contrato,
de factura y de contador. El CUPS se sustituye por un token estable (mismo CUPS y misma clave, mismo token) para
poder enlazar facturas del mismo suministro; sin la clave el token no se puede invertir.

Límite conocido (VERIFICAR): un nombre o dirección SIN etiqueta en el texto no se encuentra por patrón; el
llamante debe pasarlo en `extra` si lo conoce. Las cifras de cálculo (kWh, precios, importes, fechas, potencia)
no se tocan.
"""
import hashlib
import hmac
import re

NIF = re.compile(r"\b(?:[XYZ]\d{7}[A-Z]|\d{8}[A-Z]|[A-HJNPQRSUVW]\d{7}[0-9A-J])\b")
CUPS = re.compile(r"\bES\d{16}[A-Z]{2}(?:\d[A-Z])?\b", re.IGNORECASE)
IBAN = re.compile(r"\bES[\d*X]{2}(?:[\s-]?[\d*X]{4}){5}\b", re.IGNORECASE)
CORREO = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")

_NUM = r"(?:\s*(?:n[º°o]\.?|núm\.?|num\.?|número))?"
# Etiquetas (castellano y catalán) cuyo valor es personal. El valor llega hasta 3 espacios seguidos o fin de línea
# (el texto de `pdftotext -layout` separa columnas así).
ETIQUETAS = re.compile(
    r"(?P<etiqueta>\b(?:"
    r"titular(?: del contrato| del contracte)?|nombre|nom|raz[oó]n social|ra[oó] social"
    r"|direcci[oó]n(?: de suministro| fiscal)?|direcci[oó]|adre[cç]a(?: de subministrament| fiscal)?|domicilio"
    r"|punto de suministro|punt de subministrament"
    r"|c[oó]digo postal|codi postal|poblaci[oó]n|poblaci[oó]|localidad|municipio|municipi"
    r"|tel[eé]fono|tel[eè]fon|correo electr[oó]nico|correu electr[oò]nic|e-?mail"
    r"|contrato(?: de acceso| de suministro)?|contracte(?: d'acc[eé]s| de subministrament)?"
    r"|(?:n[º°o]\.?|n[úu]mero|n[úu]m\.?) ?(?:de )?factura|factura (?:n[º°o]\.?|n[úu]mero|n[úu]m\.?)"
    r"|n[úu]mero de contador|n[º°o]\.? de contador|n[úu]mero de comptador"
    r")" + _NUM + r"\s*:?[ \t]+)(?P<valor>\S.*?)(?=[ \t]{3,}|$)",
    re.IGNORECASE | re.MULTILINE,
)


def token_cups(cups: str, clave: bytes) -> str:
    """Token estable del suministro: HMAC del CUPS de 20 caracteres (sin el sufijo de punto de medida)."""
    if not clave:
        raise ValueError("se necesita una clave para el token del CUPS")
    base = cups.strip().upper()[:20]
    return "[CUPS:" + hmac.new(clave, base.encode(), hashlib.sha256).hexdigest()[:12] + "]"


def enmascarar(texto: str, extra: list[str] | None = None, *, clave: bytes) -> str:
    if not clave:
        raise ValueError("se necesita una clave para el token del CUPS")
    texto = ETIQUETAS.sub(lambda m: m.group("etiqueta") + "[DATO]", texto)
    texto = CUPS.sub(lambda m: token_cups(m.group(0), clave), texto)
    texto = IBAN.sub("[IBAN]", texto)
    texto = NIF.sub("[NIF]", texto)
    texto = CORREO.sub("[CORREO]", texto)
    for s in extra or []:
        if s.strip():
            texto = re.sub(re.escape(s), "[DATO]", texto, flags=re.IGNORECASE)
    return texto
