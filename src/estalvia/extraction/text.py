"""Texto local de una factura en PDF (spec #10, ticket #13).

El PDF no sale de la máquina: se convierte con `pdftotext -layout` (sin red, sin shell) y solo el texto, ya
enmascarado, llegaría a la IA. Un PDF sin capa de texto (escaneado) falla: el OCR queda fuera de esta fase.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

TIEMPO_MAXIMO_S = 60
NOMBRE_VALIDO = re.compile(r"^[\w][\w.-]*$")


class ErrorTextoPdf(RuntimeError):
    """No se pudo obtener texto del PDF; el mensaje no incluye contenido de la factura."""


def texto_de_pdf(ruta: str | Path) -> str:
    pdf = Path(ruta)
    if not pdf.is_file():
        raise ErrorTextoPdf(f"el PDF no existe: {pdf.name}")
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
        raise ErrorTextoPdf(f"pdftotext no pudo leer {pdf.name} (¿es un PDF válido?)")
    texto = resultado.stdout.decode("utf-8", errors="replace")
    if not texto.strip():
        raise ErrorTextoPdf(f"{pdf.name} no tiene capa de texto (¿escaneado?): el OCR está fuera de alcance")
    return texto


def guardar_texto(texto: str, nombre: str, *, raiz: str | Path = ".") -> Path:
    """Guarda el texto en `<raiz>/data/private/<nombre>.txt` (carpeta ignorada por git). Nada fuera de ella."""
    if not NOMBRE_VALIDO.match(nombre) or nombre.endswith("."):
        raise ValueError("nombre no válido: solo letras, dígitos, «_», «-» y «.», sin rutas")
    carpeta = Path(raiz) / "data" / "private"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{nombre}.txt"
    destino.write_text(texto, encoding="utf-8")
    destino.chmod(0o600)
    return destino
