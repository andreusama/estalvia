"""Sube y lee todas las fotos y PDFs de una carpeta (o un solo archivo) sin pasar por el formulario.

python manage.py procesar_carpeta ruta/a/fotos [--sin-leer]
"""

import mimetypes
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from prototipos.bar import servicios
from prototipos.bar.comprobaciones import comprobar
from prototipos.bar.models import Documento
from prototipos.bar.numeros import eur

EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}


class Command(BaseCommand):
    help = "Sube y lee con la IA los documentos de una carpeta de pruebas."

    def add_arguments(self, parser):
        parser.add_argument("ruta", help="Carpeta con fotos/PDF, o un archivo")
        parser.add_argument("--sin-leer", action="store_true", help="Solo subir, sin llamar a la IA")

    def handle(self, *args, ruta, sin_leer, **opts):
        base = Path(ruta).expanduser()
        if not base.exists():
            raise CommandError(f"No existe {base}")
        archivos = [base] if base.is_file() else sorted(p for p in base.iterdir() if p.suffix.lower() in EXT)
        if not archivos:
            raise CommandError("No hay fotos ni PDF en esa carpeta.")
        for p in archivos:
            mime = mimetypes.guess_type(p.name)[0] or ""
            try:
                doc, nuevo = servicios.crear_documento(p.name, mime, p.read_bytes())
            except servicios.ArchivoNoValido as e:
                self.stderr.write(f"✗ {p.name}: {e}")
                continue
            self.stdout.write(
                f"{'+' if nuevo else '='} {p.name} → documento {doc.pk}" + ("" if nuevo else " (ya estaba subido)")
            )
            if sin_leer or doc.estado == Documento.Estado.REVISADO:
                continue
            servicios.leer(doc)
            self._resumen(doc)

    def _resumen(self, doc):
        if doc.estado == Documento.Estado.ERROR:
            self.stdout.write(self.style.ERROR(f"  error: {doc.error_texto}"))
            return
        self.stdout.write(
            f"  {doc.get_tipo_display()} {doc.numero or '?'} · {doc.fecha or '?'} · {doc.proveedor_nombre or '?'} "
            f"({doc.proveedor_nif or 'sin NIF'}) · total {eur(doc.total)} · confianza {doc.confianza}"
        )
        for d in doc.campos_dudosos:
            self.stdout.write(
                f"  dudoso: {d.get('campo')}{' línea ' + str(d['linea']) if d.get('linea') else ''}: {d.get('motivo')}"
            )
        for a in doc.avisos:
            self.stdout.write(f"  aviso: {a}")
        for c in comprobar(doc):
            self.stdout.write(self.style.WARNING(f"  no cuadra: {c.texto}"))
