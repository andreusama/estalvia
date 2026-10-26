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


def test_guardar_texto_crea_el_fichero_con_permisos_600(tmp_path):
    destino = guardar_texto("x", "con-permisos", raiz=tmp_path)
    assert destino.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("nombre", ["a\n", "٣٤٥", "ａｂ", "x" * 101, "a.", "con espacio", "a\x00b"])
def test_guardar_texto_solo_admite_nombres_ascii_simples(tmp_path, nombre):
    with pytest.raises(ValueError):
        guardar_texto("x", nombre, raiz=tmp_path)


def test_guardar_texto_no_sobrescribe(tmp_path):
    guardar_texto("uno", "dup", raiz=tmp_path)
    with pytest.raises(ErrorTextoPdf, match="ya existe"):
        guardar_texto("dos", "dup", raiz=tmp_path)
    assert (tmp_path / "data" / "private" / "dup.txt").read_text() == "uno"


def test_guardar_texto_no_escribe_a_traves_de_un_enlace_simbolico_en_la_carpeta(tmp_path):
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    raiz = tmp_path / "repo"
    (raiz / "data").mkdir(parents=True)
    (raiz / "data" / "private").symlink_to(fuera)
    with pytest.raises(ErrorTextoPdf, match="enlace"):
        guardar_texto("x", "n", raiz=raiz)
    assert list(fuera.iterdir()) == []


def test_guardar_texto_no_escribe_a_traves_de_un_enlace_simbolico_en_el_fichero(tmp_path):
    carpeta = tmp_path / "data" / "private"
    carpeta.mkdir(parents=True)
    objetivo = tmp_path / "objetivo.txt"
    (carpeta / "v.txt").symlink_to(objetivo)
    with pytest.raises(ErrorTextoPdf):
        guardar_texto("x", "v", raiz=tmp_path)
    assert not objetivo.exists()


def test_guardar_texto_errores_del_sistema_son_error_texto_pdf(tmp_path):
    carpeta = tmp_path / "data" / "private"
    (carpeta / "d.txt").mkdir(parents=True)
    with pytest.raises(ErrorTextoPdf):
        guardar_texto("x", "d", raiz=tmp_path)
    with pytest.raises(ErrorTextoPdf):
        guardar_texto("\ud800", "s", raiz=tmp_path)


def test_los_mensajes_de_error_no_incluyen_el_nombre_del_fichero(tmp_path):
    secreto = "Ana-Ejemplo-ES0000000000000000AA"
    mal = tmp_path / f"{secreto}.pdf"
    mal.write_bytes(b"no es un pdf")
    sin_capa = tmp_path / f"{secreto}-2.pdf"
    sin_capa.write_bytes(pdf_minimo([]))
    for ruta in (mal, sin_capa, tmp_path / f"{secreto}-3.pdf"):
        with pytest.raises(ErrorTextoPdf) as e:
            texto_de_pdf(ruta)
        assert "Ana" not in str(e.value) and "ES0000" not in str(e.value)


def test_un_fichero_sin_cabecera_pdf_se_rechaza_sin_ejecutar_pdftotext(tmp_path, monkeypatch):
    falso = tmp_path / "x.pdf"
    falso.write_bytes(b"MZ ejecutable disfrazado")

    def no_debe_ejecutarse(*a, **k):
        raise AssertionError("no debía ejecutarse pdftotext")

    monkeypatch.setattr("subprocess.run", no_debe_ejecutarse)
    with pytest.raises(ErrorTextoPdf, match="PDF"):
        texto_de_pdf(falso)


def test_un_pdf_demasiado_grande_se_rechaza(pdf_con_texto, monkeypatch):
    monkeypatch.setattr("estalvia.extraction.text.TAMANO_MAXIMO_BYTES", 10)
    with pytest.raises(ErrorTextoPdf, match="tamaño"):
        texto_de_pdf(pdf_con_texto)


def test_tiempo_agotado_da_error_claro(pdf_con_texto, monkeypatch):
    import subprocess

    def lento(*a, **k):
        raise subprocess.TimeoutExpired("pdftotext", 1)

    monkeypatch.setattr("subprocess.run", lento)
    with pytest.raises(ErrorTextoPdf, match="tardó"):
        texto_de_pdf(pdf_con_texto)
