"""Texto local de un PDF con pdftotext (spec #10, ticket #13). PDFs sintéticos generados en el test."""
import shutil
from pathlib import Path

import pytest

from estalvia.extraction.text import ErrorTextoPdf, guardar_texto, texto_de_pdf

pytestmark = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext no está instalado")


def pdf_minimo(lineas: list[tuple[int, int, str]]) -> bytes:
    """PDF de una página con texto en (x, y); sin lineas, la página queda vacía (sin capa de texto)."""
    flujo = "".join(f"BT /F1 10 Tf {x} {y} Td ({t}) Tj ET\n" for x, y, t in lineas).encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(flujo)).encode() + b" >>\nstream\n" + flujo + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida, posiciones = b"%PDF-1.4\n", []
    for n, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{n} 0 obj\n".encode() + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    salida += b"".join(f"{p:010d} 00000 n \n".encode() for p in posiciones)
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return salida


@pytest.fixture
def pdf_con_texto(tmp_path) -> Path:
    ruta = tmp_path / "factura-sintetica.pdf"
    ruta.write_bytes(pdf_minimo([(50, 780, "Potencia contratada P1"), (350, 780, "4,400 kW"),
                                 (50, 760, "Energia P1"), (350, 760, "31,25 kWh")]))
    return ruta


def test_devuelve_el_texto_conservando_las_columnas(pdf_con_texto):
    texto = texto_de_pdf(pdf_con_texto)
    primera = next(x for x in texto.splitlines() if "Potencia" in x)
    assert "Potencia contratada P1" in primera and primera.rstrip().endswith("4,400 kW")
    assert len(primera.split("P1")[1].split("4,400")[0]) >= 2  # el hueco entre columnas se conserva
    assert "31,25 kWh" in texto


def test_pdf_sin_capa_de_texto_dice_que_el_ocr_esta_fuera_de_alcance(tmp_path):
    ruta = tmp_path / "escaneada.pdf"
    ruta.write_bytes(pdf_minimo([]))
    with pytest.raises(ErrorTextoPdf, match="OCR"):
        texto_de_pdf(ruta)


def test_pdftotext_ausente_da_un_error_claro(pdf_con_texto, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(ErrorTextoPdf, match="pdftotext"):
        texto_de_pdf(pdf_con_texto)


def test_fichero_que_no_es_pdf_o_no_existe_da_error_claro(tmp_path):
    falso = tmp_path / "x.pdf"
    falso.write_bytes(b"esto no es un pdf")
    with pytest.raises(ErrorTextoPdf):
        texto_de_pdf(falso)
    with pytest.raises(ErrorTextoPdf, match="no existe"):
        texto_de_pdf(tmp_path / "nada.pdf")


def test_ruta_que_empieza_por_guion_no_se_interpreta_como_opcion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("-raro.pdf").write_bytes(pdf_minimo([(50, 780, "Hola 1,00 kWh")]))
    assert "Hola" in texto_de_pdf("-raro.pdf")


def test_guardar_texto_escribe_solo_bajo_data_private(tmp_path):
    destino = guardar_texto("contenido", "factura-1", raiz=tmp_path)
    assert destino == tmp_path / "data" / "private" / "factura-1.txt"
    assert destino.read_text(encoding="utf-8") == "contenido"


@pytest.mark.parametrize("nombre", ["../fuera", "a/b", "/abs", "", ".", "..", "a\\b"])
def test_guardar_texto_rechaza_nombres_que_salen_de_la_carpeta(tmp_path, nombre):
    with pytest.raises(ValueError):
        guardar_texto("x", nombre, raiz=tmp_path)
    assert not any(p.is_file() for p in tmp_path.rglob("*"))
