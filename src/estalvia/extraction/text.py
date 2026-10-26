"""Texto local de una factura en PDF (spec #10, ticket #13).

El PDF no sale de la máquina: se convierte con `pdftotext -layout` (sin red, sin shell) y solo el texto, ya
enmascarado, llegaría a la IA. Un PDF sin capa de texto (escaneado) falla: el OCR queda fuera de esta fase.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

TIEMPO_MAXIMO_S = 60
TAMANO_MAXIMO_BYTES = 20 * 1024 * 1024
NOMBRE_VALIDO = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}")


class ErrorTextoPdf(RuntimeError):
    """No se pudo obtener texto del PDF; los mensajes no incluyen contenido ni el nombre del fichero (puede llevar
    el nombre del cliente o un CUPS)."""


def texto_de_pdf(ruta: str | Path) -> str:
    pdf = Path(ruta)
    if not pdf.is_file():
        raise ErrorTextoPdf("el PDF no existe o no es un fichero")
    if pdf.stat().st_size > TAMANO_MAXIMO_BYTES:
        raise ErrorTextoPdf(f"el PDF supera el tamaño máximo de {TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB")
    with pdf.open("rb") as f:
        if b"%PDF-" not in f.read(1024):
            raise ErrorTextoPdf("el fichero no parece un PDF")
    ejecutable = shutil.which("pdftotext")
    if ejecutable is None:
        raise ErrorTextoPdf("pdftotext no está instalado (paquete poppler-utils)")
    try:
        # Ruta absoluta: una ruta que empiece por «-» no se interpretaría como opción.
        resultado = subprocess.run([ejecutable, "-layout", str(pdf.resolve()), "-"], capture_output=True,
                                   timeout=TIEMPO_MAXIMO_S, check=False)
    except subprocess.TimeoutExpired:
        raise ErrorTextoPdf(f"pdftotext tardó más de {TIEMPO_MAXIMO_S} s") from None
    if resultado.returncode != 0:
        raise ErrorTextoPdf("pdftotext no pudo leer el PDF (¿está dañado o protegido?)")
    texto = resultado.stdout.decode("utf-8", errors="replace")
    if not texto.strip():
        raise ErrorTextoPdf("el PDF no tiene capa de texto (¿escaneado?): el OCR está fuera de alcance")
    return texto


def guardar_texto(texto: str, nombre: str, *, raiz: str | Path = ".") -> Path:
    """Guarda el texto en `<raiz>/data/private/<nombre>.txt` (carpeta ignorada por git). Nada fuera de ella:
    no sigue enlaces simbólicos, no sobrescribe y crea el fichero ya con permisos 600."""
    if not NOMBRE_VALIDO.fullmatch(nombre) or nombre.endswith("."):
        raise ValueError("nombre no válido: 1-100 caracteres ASCII (letras, dígitos, «_», «-», «.»), sin rutas")
    raiz = Path(raiz)
    for parte in (raiz / "data", raiz / "data" / "private"):
        if parte.is_symlink():
            raise ErrorTextoPdf("data o data/private es un enlace simbólico; no se escribe a través de él")
    carpeta = raiz / "data" / "private"
    try:
        datos = texto.encode("utf-8")
        carpeta.mkdir(parents=True, exist_ok=True)
        # O_EXCL no sigue enlaces y falla si el destino existe (fichero, directorio o enlace colgante).
        fd = os.open(carpeta / f"{nombre}.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise ErrorTextoPdf("el fichero ya existe; no se sobrescribe") from None
    except (OSError, UnicodeEncodeError) as e:
        raise ErrorTextoPdf(f"no se pudo guardar el texto ({type(e).__name__})") from None
    with os.fdopen(fd, "wb") as f:
        f.write(datos)
    return carpeta / f"{nombre}.txt"
