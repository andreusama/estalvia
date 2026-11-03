"""Lectura de un documento con la API de Anthropic (visión + salida estructurada por JSON schema).

La IA solo transcribe lo impreso: no calcula, no corrige y deja en blanco lo que no ve. Las cuentas las hace `comprobaciones.py`.
Sonnet 5.5 rechaza `tool_choice` forzado, así que se usa `output_config.format` (documentación de la API, nov 2026).
"""

import base64
import json
import logging
import os

import anthropic

log = logging.getLogger(__name__)

MODELO = os.environ.get("ESTALVIA_MODELO", "claude-sonnet-5-5")
VERSION_PROMPT = "2026-11-02.1"

CAMPOS_DUDOSOS = [
    "tipo",
    "numero",
    "fecha",
    "vencimiento",
    "proveedor_nombre",
    "proveedor_nif",
    "proveedor_iban",
    "cliente_nombre",
    "cliente_nif",
    "forma_pago",
    "base_imponible",
    "total",
    "iva",
    "linea_descripcion",
    "linea_cantidad",
    "linea_precio_unitario",
    "linea_importe",
    "referencias_albaran",
    "otro",
]


def _objeto(**props) -> dict:
    return {"type": "object", "additionalProperties": False, "properties": props, "required": list(props)}


SCHEMA = _objeto(
    tipo={"type": "string", "enum": ["albaran", "factura", "ticket", "abono", "desconocido"]},
    proveedor=_objeto(
        nombre={"type": "string"}, nif={"type": "string"}, direccion={"type": "string"}, iban={"type": "string"}
    ),
    cliente=_objeto(nombre={"type": "string"}, nif={"type": "string"}),
    numero={"type": "string"},
    fecha={"type": "string"},
    vencimiento={"type": "string"},
    forma_pago={"type": "string"},
    lineas={
        "type": "array",
        "items": _objeto(
            codigo={"type": "string"},
            descripcion={"type": "string"},
            cantidad={"type": "string"},
            unidad={"type": "string"},
            precio_unitario={"type": "string"},
            descuento={"type": "string"},
            importe={"type": "string"},
        ),
    },
    referencias_albaran={"type": "array", "items": _objeto(numero={"type": "string"}, fecha={"type": "string"})},
    iva={"type": "array", "items": _objeto(tipo={"type": "string"}, base={"type": "string"}, cuota={"type": "string"})},
    base_imponible={"type": "string"},
    total={"type": "string"},
    confianza={"type": "string", "enum": ["alta", "media", "baja"]},
    campos_dudosos={
        "type": "array",
        "items": _objeto(
            campo={"type": "string", "enum": CAMPOS_DUDOSOS}, linea={"type": "integer"}, motivo={"type": "string"}
        ),
    },
    avisos={"type": "array", "items": {"type": "string"}},
)

PROMPT = """Lees fotos y PDFs de albaranes, facturas y tickets de proveedores de un bar o restaurante en España y devuelves \
los datos en el esquema indicado. Eres un transcriptor, no un contable.

Reglas:
- Copia lo que está impreso, tal cual. Nunca calcules, corrijas, redondees ni completes un importe, una fecha o un número. \
Si algo no aparece o no se lee con seguridad, déjalo como cadena vacía (""; en linea, 0) y añade una entrada en campos_dudosos con el motivo (por ejemplo «dígitos borrosos»). \
Si lo lees pero dudas de un dígito, ponlo y márcalo como dudoso.
- Importes y cantidades como texto con punto decimal, sin símbolo de moneda ni separador de miles (12.69). Fechas como AAAA-MM-DD.
- tipo: factura si el documento se titula o rotula Factura; albarán si es un albarán o nota de entrega; ticket si es un comprobante \
de caja; abono si es una factura rectificativa o nota de crédito; desconocido si no puedes decidirlo. Si tienes que decidir entre \
dos, elige el que indica el rótulo del documento y márcalo como dudoso.
- proveedor es quien emite el documento; cliente es el comprador (el bar).
- En las facturas, una fila de la tabla que cita un albarán («Albarán A.28541 Fecha 21/10/2026») NO es una línea de producto: va en \
referencias_albaran con el número tal como está impreso, y sus productos son las líneas que vienen debajo.
- lineas: una por producto, en orden. descuento es el porcentaje impreso si existe. No inventes unidades: si no hay, cadena vacía.
- iva: una entrada por tipo impositivo con su base y su cuota impresas. base_imponible y total, los impresos.
- campos_dudosos: campo es uno del listado permitido; si afecta a una línea, pon su número (1 es la primera) en linea.
- confianza: alta si todo se lee con claridad, baja si el documento está borroso, cortado o incompleto.
- avisos: cualquier cosa que deba saber quien revise (hojas solapadas, foto cortada, escritura a mano, documento girado)."""


class ErrorLectura(Exception):
    """Mensaje pensado para enseñarse al usuario; el detalle técnico va al log."""


def crear_cliente() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ErrorLectura("Falta configurar la clave de la IA (ANTHROPIC_API_KEY).")
    return anthropic.Anthropic(max_retries=2, timeout=110.0)


def _bloque(contenido: bytes, mime: str) -> dict:
    datos = base64.standard_b64encode(contenido).decode()
    tipo = "document" if mime == "application/pdf" else "image"
    return {"type": tipo, "source": {"type": "base64", "media_type": mime, "data": datos}}


def extraer(contenido: bytes, mime: str) -> tuple[dict, dict]:
    """Devuelve (datos según SCHEMA, metadatos de la llamada). Lanza ErrorLectura con un texto presentable."""
    cliente = crear_cliente()
    try:
        resp = cliente.messages.create(
            model=MODELO,
            max_tokens=16000,
            system=PROMPT,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[
                {"role": "user", "content": [_bloque(contenido, mime), {"type": "text", "text": "Lee este documento."}]}
            ],
        )
    except ErrorLectura:
        raise
    except anthropic.RateLimitError as e:
        log.warning("IA: límite de uso %s", getattr(e, "_request_id", ""))
        raise ErrorLectura("La IA está saturada ahora mismo. Inténtalo de nuevo en un minuto.") from e
    except anthropic.AuthenticationError as e:
        raise ErrorLectura("La clave de la IA no es válida.") from e
    except anthropic.BadRequestError as e:
        log.warning("IA: petición rechazada: %s", e.message)
        raise ErrorLectura(
            "La IA no ha aceptado esta petición (¿el archivo está dañado o es demasiado grande?)."
        ) from e
    except Exception as e:  # red, timeouts, 5xx: el usuario solo necesita saber que se puede reintentar
        log.exception("IA: fallo de la llamada")
        raise ErrorLectura("No se pudo contactar con la IA. Inténtalo de nuevo.") from e

    if resp.stop_reason == "refusal":
        raise ErrorLectura("La IA se ha negado a leer este documento.")
    if resp.stop_reason == "max_tokens":
        raise ErrorLectura("El documento es demasiado largo para leerlo de una vez.")
    texto = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        datos = json.loads(texto)
    except ValueError as e:
        log.error("IA: respuesta que no es JSON")
        raise ErrorLectura("La IA ha devuelto una respuesta que no se entiende. Inténtalo de nuevo.") from e
    uso = {"entrada": resp.usage.input_tokens, "salida": resp.usage.output_tokens}
    return datos, {"modelo": resp.model, "uso": uso}
