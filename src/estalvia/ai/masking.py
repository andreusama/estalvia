"""Enmascarado previo al envío de texto al proveedor de IA (TDD sección 9, límite 7; spec #10, ticket #12).

Quita lo que no hace falta para calcular: nombre, dirección, teléfono, correo, NIF, IBAN, números de contrato,
de factura y de contador. El CUPS se sustituye por un token estable (mismo CUPS y misma clave, mismo token) para
poder enlazar facturas del mismo suministro; sin la clave el token no se puede invertir.

Principio: una cifra de cálculo (kWh, precios, importes, fechas, potencia) nunca se enmascara; ante la duda entre
dejar un dato personal y borrar una cifra, pesa más la cifra porque su pérdida lleva a Revisión y se ve.
Por eso las etiquetas genéricas (nombre, contrato, factura...) solo valen con «:» pegado a la etiqueta, y un valor
que parece una cifra o una fecha no se toca.

Límites conocidos (VERIFICAR con facturas reales): un nombre o dirección SIN etiqueta ni tratamiento («Sr.»), o con
el valor en la línea siguiente a la etiqueta, no se encuentra por patrón: el llamante debe pasarlo en `extra`.
"""
import hashlib
import hmac
import re

_LET = r"[A-Za-zÁÉÍÓÚÀÈÒÜÇÑáéíóúàèòüçñ]"
_MAY = r"[A-ZÁÉÍÓÚÀÈÒÜÇÑ]"
_NUM = r"(?:n\.?\s?[º°]\.?|n[úu]m(?:ero|\.)?)"  # «nº», «N.º», «núm.», «número»

CUPS = re.compile(r"\bES(?:[ ]?\d){16}[ ]?[A-Z]{2}(?:\d[A-Z]{1,2}\d?)?\b", re.IGNORECASE)
IBAN = re.compile(r"\bES[\d*X]{2}(?:[ -]?[\d*X]){20}\b", re.IGNORECASE)
NIF = re.compile(r"\b(?:[XYZ]-?\d{7}-?[A-Z]|\d{8}-?[A-Z]|[A-HJNPQRSUVW]-?\d{7}-?[0-9A-J])\b", re.IGNORECASE)
CORREO = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
TELEFONO = re.compile(
    r"(?<![\d,.-])(?:\+34[ -]?\d{9}"
    r"|(?:\+34[ -]?)?(?:[6-9]\d{2}[ -]\d{2}[ -]\d{2}[ -]\d{2}|[89]\d[ -]?\d{3}[ -]?\d{2}[ -]\d{2}))\b")
TRATAMIENTO = re.compile(
    rf"\b(?:Sr\.|Sra\.|Sres\.|Don|Doña|Dña\.|Dª|Senyor|Senyora)[ ]+(?:{_MAY}[\w'-]*[ ]?){{1,4}}")
CODIGO_POSTAL_Y_POBLACION = re.compile(
    rf"\b(?:0[1-9]|[1-4]\d|5[0-2])\d{{3}}(?:,[ ]*|[ ]+){_MAY}[\w.'-]+(?:,?[ ]+{_MAY}[\w.'-]+){{0,3}}")
# Calle: abreviatura o tipo de vía con mayúscula inicial al comienzo de un tramo de línea (hasta 3 espacios o el fin).
CALLE = re.compile(
    r"(?<![\w/])(?:CL|C/|Calle|CALLE|Carrer|CARRER|Avda\.?|AVDA\.?|Avenida|AVENIDA|Avinguda|AVINGUDA|Plaza|PLAZA"
    r"|Plaça|PLAÇA|Paseo|PASEO|Passeig|PASSEIG)(?:[ ]{1,2}|(?<=/))\S.*?(?=[ ]{3,}|\t|$)", re.MULTILINE)



def _sustituir_calle(m: re.Match) -> str:
    """Solo es dirección si lleva número y no parece una línea de cálculo (unidad, importe o «:»)."""
    t = m.group(0)
    if not re.search(r"\d", t) or _CON_UNIDAD.search(t) or ":" in t:
        return t
    return "[DIRECCION]"


# Etiquetas cuyo valor es personal y que exigen «:» pegado a la etiqueta (castellano y catalán).
_ETIQUETAS_CON_DOS_PUNTOS = "|".join([
    r"titular(?: del contrato| del contracte)?", r"cliente|client", r"nombre|nom", r"raz[oó]n social|ra[oó] social",
    r"direcci[oó]n(?: de (?:suministro|env[ií]o)| fiscal)?|direcci[oó]|adre[cç]a(?: de (?:subministrament|enviament)"
    r"| fiscal)?|domicilio|domicili",
    r"punto de suministro|punt de subministrament", r"c[oó]digo postal|codi postal|c\.?p\.?",
    r"poblaci[oó]n|poblaci[oó]|localidad|municipio|municipi|provincia|prov[ií]ncia",
    r"tel[eé]fono|tel[eè]fon|tel\.|telf\.?|m[oó]vil|m[òo]bil|fax",
    r"correo electr[oó]nico|correu electr[oò]nic|e-?mail",
    r"referencia catastral|refer[eè]ncia cadastral|referencia de pago",
    r"(?:n[úu]mero de )?contra(?:to|cte)(?: de acceso| d['’]acc[eé]s)?",
    r"(?<!total )(?<!importe )factura|contador|comptador",
])
CON_DOS_PUNTOS = re.compile(
    rf"(?P<etiqueta>\b(?:{_ETIQUETAS_CON_DOS_PUNTOS})[ \t]*:[ \t]*)(?P<valor>\S.*?)(?=[ \t]{{3,}}|\t|$)",
    re.IGNORECASE | re.MULTILINE)

# La misma etiqueta con «:» al final de la línea y el valor en la siguiente (pdftotext -layout lo hace a menudo).
EN_LINEA_SIGUIENTE = re.compile(
    rf"(?P<etiqueta>\b(?:{_ETIQUETAS_CON_DOS_PUNTOS})[ \t]*:[ \t]*\n[ \t\n]*)(?P<valor>\S.*?)(?=[ \t]{{3,}}|\t|$)",
    re.IGNORECASE | re.MULTILINE)

# Etiquetas con «nº»/«número»: el valor es una sola palabra y debe llevar algún dígito.
_ETIQUETAS_CON_NUMERO = "|".join([
    rf"(?:contrato|contracte)(?: de acceso| d['’]acc[eé]s| de suministro| de subministrament)?[ ]*{_NUM}",
    rf"{_NUM}[ ]*de[ ]+(?:factura|contador|comptador|serie(?: del contador)?)",
    rf"factura[ ]*{_NUM}", rf"equipo de medida[ ]*{_NUM}",
])
CON_NUMERO = re.compile(
    rf"(?P<etiqueta>\b(?:{_ETIQUETAS_CON_NUMERO})[ \t]*:?[ \t]*)(?P<valor>(?=\S*\d)\S+)", re.IGNORECASE)

# «Lectures del comptador 123456789»: el número de serie del contador (6 o más dígitos seguidos).
CON_COMPTADOR = re.compile(
    r"(?P<etiqueta>\b(?:lectures del comptador|lecturas del contador)[ \t]*:?[ \t]*)(?P<valor>(?=\S*\d{6})\S+)",
    re.IGNORECASE)

_FECHA = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")
_CON_UNIDAD = re.compile(r"(?<![\d.,])\d[\d.,]*[ ]*(?:kwh|kw|kva|kvarh|€|eur|%)", re.IGNORECASE)
_DECIMAL = re.compile(r"^-?\d[\d.]*,\d+$|^-?\d+\.\d+$")


def _exigir_clave(clave: bytes) -> None:
    if isinstance(clave, str):
        raise TypeError("la clave debe ser bytes, no str")
    if not clave:
        raise ValueError("se necesita una clave para el token del CUPS")


def _es_cifra(valor: str) -> bool:
    """Cifra de cálculo o ya enmascarado: no se vuelve a tocar."""
    v = valor.strip()
    return bool(_FECHA.search(v) or _CON_UNIDAD.search(v) or _DECIMAL.match(v) or "[CUPS:" in v)


def _sustituir_valor(m: re.Match) -> str:
    return m.group(0) if _es_cifra(m.group("valor")) else m.group("etiqueta") + "[DATO]"


def token_cups(cups: str, clave: bytes) -> str:
    """Token estable del suministro: HMAC del CUPS de 20 caracteres (sin espacios ni sufijo de punto de medida).
    12 hex = 48 bits: basta para distinguir los suministros de un operador; no es una identidad global."""
    _exigir_clave(clave)
    base = re.sub(r"\s", "", cups).upper()[:20]
    return "[CUPS:" + hmac.new(clave, base.encode(), hashlib.sha256).hexdigest()[:12] + "]"


def enmascarar(texto: str, extra: list[str] | None = None, *, clave: bytes) -> str:
    _exigir_clave(clave)
    for s in extra or []:  # primero: un valor conocido se quita entero antes de que un patrón lo parta
        if s.strip():
            texto = re.sub(r"\s+".join(map(re.escape, s.split())), "[DATO]", texto, flags=re.IGNORECASE)
    texto = CUPS.sub(lambda m: token_cups(m.group(0), clave), texto)
    texto = IBAN.sub("[IBAN]", texto)
    texto = NIF.sub("[NIF]", texto)
    texto = CON_NUMERO.sub(_sustituir_valor, texto)
    texto = CON_COMPTADOR.sub(_sustituir_valor, texto)
    texto = CON_DOS_PUNTOS.sub(_sustituir_valor, texto)
    texto = EN_LINEA_SIGUIENTE.sub(_sustituir_valor, texto)
    texto = CALLE.sub(_sustituir_calle, texto)
    texto = TRATAMIENTO.sub("[NOMBRE]", texto)
    texto = CODIGO_POSTAL_Y_POBLACION.sub("[DATO]", texto)
    texto = TELEFONO.sub("[TELEFONO]", texto)
    return CORREO.sub("[CORREO]", texto)


_SELLO = object()


class TextoEnmascarado(str):
    """Texto que ya ha pasado por `enmascarar`. Solo se crea con `sellar`: la pasarela de IA no acepta otro."""
    __slots__ = ()

    def __new__(cls, valor: str, *, _sello: object = None):
        if _sello is not _SELLO:
            raise TypeError("TextoEnmascarado solo se crea con sellar(): el texto debe pasar por enmascarar")
        return super().__new__(cls, valor)


def sellar(texto: str, extra: list[str] | None = None, *, clave: bytes) -> TextoEnmascarado:
    return TextoEnmascarado(enmascarar(texto, extra, clave=clave), _sello=_SELLO)
