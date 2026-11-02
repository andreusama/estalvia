"""Subir, leer y revisar documentos. Todo lo que toca la base de datos del flujo vive aquí."""

import hashlib
from datetime import date

from django.db import transaction
from django.utils import timezone

from . import extraccion
from .models import DesgloseIva, Documento, Evento, Linea, Proveedor, ReferenciaAlbaran
from .numeros import a_decimal, ajustar, normalizar_referencia

MAX_BYTES = 4 * 1024 * 1024  # Vercel rechaza cuerpos de más de 4,5 MB
MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
MAX_LINEAS = 200


class ArchivoNoValido(Exception):
    pass


def registrar(doc: Documento, tipo: str, detalle: str = "") -> None:
    Evento.objects.create(documento=doc, tipo=tipo, detalle=detalle[:2000])


def crear_documento(nombre: str, mime: str, contenido: bytes) -> tuple[Documento, bool]:
    """Guarda el archivo original. Devuelve (documento, es_nuevo); un archivo idéntico no se guarda dos veces."""
    if mime not in MIMES:
        raise ArchivoNoValido("Solo se admiten fotos (JPG, PNG, WebP) y PDF.")
    if not contenido:
        raise ArchivoNoValido("El archivo está vacío.")
    if len(contenido) > MAX_BYTES:
        raise ArchivoNoValido("El archivo pesa más de 4 MB. Haz la foto con menos calidad o recórtala.")
    sha = hashlib.sha256(contenido).hexdigest()
    existente = Documento.objects.filter(sha256=sha).first()
    if existente:
        return existente, False
    with transaction.atomic():
        doc = Documento.objects.create(archivo=contenido, nombre_archivo=nombre[:255], tipo_mime=mime, sha256=sha)
        registrar(doc, "subido", f"{nombre} ({len(contenido) // 1024} KB)")
    return doc, True


def _texto(valor, largo: int) -> str:
    return (valor or "").strip()[:largo] if isinstance(valor, str) else ""


def _fecha(valor) -> date | None:
    try:
        return date.fromisoformat(valor) if valor else None
    except (TypeError, ValueError):
        return None


def aplicar_datos(doc: Documento, datos: dict) -> None:
    """Vuelca lo que dijo la IA en el documento tal cual (sin corregir nada) y guarda la respuesta original."""
    prov, cli = datos.get("proveedor") or {}, datos.get("cliente") or {}
    tipos = {t.value for t in Documento.Tipo}
    doc.tipo = datos.get("tipo") if datos.get("tipo") in tipos else Documento.Tipo.DESCONOCIDO
    doc.proveedor_nombre = _texto(prov.get("nombre"), 200)
    doc.proveedor_nif = _texto(prov.get("nif"), 20)
    doc.proveedor_iban = _texto(prov.get("iban"), 40)
    doc.cliente_nombre = _texto(cli.get("nombre"), 200)
    doc.cliente_nif = _texto(cli.get("nif"), 20)
    doc.numero = _texto(datos.get("numero"), 60)
    doc.fecha, doc.vencimiento = _fecha(datos.get("fecha")), _fecha(datos.get("vencimiento"))
    doc.forma_pago = _texto(datos.get("forma_pago"), 120)
    doc.base_imponible = ajustar(a_decimal(datos.get("base_imponible")), 12, 2)
    doc.total = ajustar(a_decimal(datos.get("total")), 12, 2)
    doc.confianza = datos.get("confianza") if datos.get("confianza") in ("alta", "media", "baja") else "baja"
    doc.campos_dudosos = [d for d in datos.get("campos_dudosos") or [] if isinstance(d, dict)]
    doc.avisos = [str(a)[:300] for a in datos.get("avisos") or []]
    doc.respuesta_ia = datos

    doc.lineas.all().delete()
    doc.referencias.all().delete()
    doc.desglose_iva.all().delete()
    for orden, li in enumerate((datos.get("lineas") or [])[:MAX_LINEAS], start=1):
        Linea.objects.create(
            documento=doc,
            orden=orden,
            codigo=_texto(li.get("codigo"), 60),
            descripcion=_texto(li.get("descripcion"), 300),
            cantidad=ajustar(a_decimal(li.get("cantidad")), 12, 3),
            unidad=_texto(li.get("unidad"), 30),
            precio_unitario=ajustar(a_decimal(li.get("precio_unitario")), 12, 4),
            descuento=ajustar(a_decimal(li.get("descuento")), 7, 2),
            importe=ajustar(a_decimal(li.get("importe")), 12, 2),
        )
    for ref in datos.get("referencias_albaran") or []:
        numero = _texto(ref.get("numero"), 60)
        if numero:
            ReferenciaAlbaran.objects.create(
                documento=doc,
                numero=numero,
                fecha=_fecha(ref.get("fecha")),
                numero_normalizado=normalizar_referencia(numero),
            )
    for fila in datos.get("iva") or []:
        tipo = ajustar(a_decimal(fila.get("tipo")), 5, 2)
        if tipo is not None:
            DesgloseIva.objects.create(
                documento=doc,
                tipo=tipo,
                base=ajustar(a_decimal(fila.get("base")), 12, 2),
                cuota=ajustar(a_decimal(fila.get("cuota")), 12, 2),
            )


def leer(doc: Documento) -> Documento:
    """Lee un documento por pendiente o con error. Un documento ya leído o revisado no se pisa."""
    if doc.estado not in (Documento.Estado.PENDIENTE, Documento.Estado.ERROR):
        return doc
    try:
        datos, meta = extraccion.extraer(bytes(doc.archivo), doc.tipo_mime)
    except extraccion.ErrorLectura as e:
        doc.estado, doc.error_texto = Documento.Estado.ERROR, str(e)
        doc.save(update_fields=["estado", "error_texto"])
        registrar(doc, "error", str(e))
        return doc
    with transaction.atomic():
        aplicar_datos(doc, datos)
        doc.estado, doc.error_texto = Documento.Estado.PROCESADO, ""
        doc.modelo_ia, doc.version_prompt, doc.leido_en = meta["modelo"], extraccion.VERSION_PROMPT, timezone.now()
        doc.save()
        registrar(doc, "leido", f"{meta['modelo']} · {meta['uso']['entrada']} + {meta['uso']['salida']} tokens")
    return doc


def _nif(texto: str) -> str:
    return "".join(c for c in texto.upper() if c.isalnum())


def vincular_proveedor(doc: Documento) -> None:
    """Al revisar, enlaza el documento con un proveedor existente (por NIF, o por nombre) o crea uno."""
    nombre, nif = doc.proveedor_nombre.strip(), _nif(doc.proveedor_nif)
    if not nombre and not nif:
        doc.proveedor = None
        return
    prov = None
    if nif:
        prov = next(
            (p for p in Proveedor.objects.filter(nif__isnull=False).exclude(nif="") if _nif(p.nif) == nif), None
        )
    if prov is None and nombre:
        prov = Proveedor.objects.filter(nombre__iexact=nombre).first()
    if prov is None:
        prov = Proveedor.objects.create(nombre=nombre or nif, nif=nif)
    elif nif and not prov.nif:
        prov.nif = nif
        prov.save(update_fields=["nif"])
    doc.proveedor = prov


def marcar_revisado(doc: Documento) -> None:
    vincular_proveedor(doc)
    doc.estado, doc.revisado_en = Documento.Estado.REVISADO, timezone.now()
    doc.save()
    registrar(doc, "revisado", "Revisado por una persona")
