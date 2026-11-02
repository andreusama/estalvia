"""Leer el extracto del banco y guardarlo sin duplicados. Todo con extractos SINTÉTICOS (inventados)."""

from datetime import date
from decimal import Decimal as D

import pytest

from prototipos.bar import extracto
from prototipos.bar.models import Movimiento, PerfilImportacion

pytestmark = pytest.mark.django_db

CSV = (
    "Fecha;Concepto;Importe;Saldo\n"
    "01/10/2026;TPV VENTAS TARJETAS 01/10;1.184,30;5.434,30\n"
    "05/10/2026;RECIBO LUZ LOCAL;-312,45;5.121,85\n"
    "28/10/2026;TRANSF A DISTRIBUCIONES EJEMPLO SL FRA F26-00001;-12,69;5.109,16\n"
)


@pytest.fixture
def perfil():
    return PerfilImportacion.por_defecto()


def test_lee_un_extracto_a_la_espanola(perfil):
    lectura = extracto.leer_extracto(CSV.encode(), perfil)
    assert lectura.errores == []
    assert [(f.fecha, f.importe, f.saldo) for f in lectura.filas] == [
        (date(2026, 10, 1), D("1184.30"), D("5434.30")),
        (date(2026, 10, 5), D("-312.45"), D("5121.85")),
        (date(2026, 10, 28), D("-12.69"), D("5109.16")),
    ]
    assert lectura.filas[2].concepto == "TRANSF A DISTRIBUCIONES EJEMPLO SL FRA F26-00001"


def test_salta_las_lineas_de_titulo_antes_de_la_cabecera(perfil):
    texto = "Extracto de cuenta;;;\nCliente: BAR DE PRUEBA;;;\n\n" + CSV
    assert len(extracto.leer_extracto(texto.encode(), perfil).filas) == 3


def test_admite_ficheros_en_windows_latin1(perfil):
    texto = CSV.replace("RECIBO LUZ LOCAL", "RECIBO ALQUILER JULIÁN")
    lectura = extracto.leer_extracto(texto.encode("cp1252"), perfil)
    assert lectura.filas[1].concepto == "RECIBO ALQUILER JULIÁN"


def test_detecta_la_coma_como_separador_y_respeta_las_comillas():
    perfil = PerfilImportacion.por_defecto()
    perfil.sep_miles, perfil.sep_decimal = ",", "."
    texto = 'Fecha,Concepto,Importe,Saldo\n01/10/2026,"PAGO, CON COMA",-1,240.50,100.00\n'.replace(
        "-1,240.50", '"-1,240.50"'
    )
    fila = extracto.leer_extracto(texto.encode(), perfil).filas[0]
    assert (fila.concepto, fila.importe) == ("PAGO, CON COMA", D("-1240.50"))


def test_falta_una_columna_y_se_dice_cuales_trae_el_fichero(perfil):
    with pytest.raises(extracto.ExtractoNoValido) as e:
        extracto.leer_extracto(b"Dia;Detalle;Cantidad\n01/10/2026;X;1,00\n", perfil)
    assert "«Fecha»" in str(e.value) and "Dia, Detalle, Cantidad" in str(e.value)
    with pytest.raises(extracto.ExtractoNoValido):
        extracto.leer_extracto(b"   \n", perfil)


def test_una_fila_ilegible_se_avisa_con_su_linea_y_no_tumba_las_demas(perfil):
    texto = (
        CSV
        + "31/02/2026;FECHA IMPOSIBLE;-1,00;1,00\n02/11/2026;TRES DECIMALES;-1,005;1,00\n03/11/2026;SIN IMPORTE;;1,00\n"
    )
    lectura = extracto.leer_extracto(texto.encode(), perfil)
    assert len(lectura.filas) == 3
    assert [e.linea for e in lectura.errores] == [5, 6, 7]
    assert "fecha" in lectura.errores[0].motivo and "decimales" in lectura.errores[1].motivo


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("-1.240,50", "-1240.50"), ("(12,50)", "-12.50"), ("12,50-", "-12.50"), ("1 240,50 €", "1240.50"),
        ("1\xa0240,50", "1240.50"), ("+3,00", "3.00"), ("0,05", "0.05"), ("1240,5", "1240.50"), ("7", "7.00"),
    ],
)  # fmt: skip
def test_importes_a_la_espanola(perfil, texto, esperado):
    if " " in texto or "\xa0" in texto:
        perfil.sep_miles = " "
    assert extracto.leer_importe(texto, perfil) == D(esperado)


@pytest.mark.parametrize("texto", ["1240.50", "12,345", "abc", "1.24,50", "12,50,3"])
def test_importes_que_no_encajan_con_el_formato_se_rechazan_en_vez_de_adivinar(perfil, texto):
    with pytest.raises(ValueError):
        extracto.leer_importe(texto, perfil)


def test_cargos_y_abonos_en_dos_columnas(perfil):
    perfil.col_importe, perfil.col_abono, perfil.col_saldo = "Cargo", "Abono", ""
    texto = "Fecha;Concepto;Cargo;Abono\n01/10/2026;PAGO;12,50;\n02/10/2026;DEVOLUCION;;3,00\n"
    assert [f.importe for f in extracto.leer_extracto(texto.encode(), perfil).filas] == [D("-12.50"), D("3.00")]


def test_si_el_concepto_esta_vacio_usa_el_de_reserva(perfil):
    perfil.col_concepto_aux = "Detalle"
    texto = "Fecha;Concepto;Detalle;Importe\n01/10/2026;;COMPRA EN TIENDA;-5,00\n"
    assert extracto.leer_extracto(texto.encode(), perfil).filas[0].concepto == "COMPRA EN TIENDA"


# ---- Deduplicación: reimportar nunca duplica ----


def test_reimportar_el_mismo_fichero_no_crea_duplicados(perfil):
    primero = extracto.importar_extracto(perfil, "oct.csv", CSV.encode())
    segundo = extracto.importar_extracto(perfil, "oct.csv", CSV.encode())
    assert (primero.nuevos, primero.repetidos, segundo.nuevos, segundo.repetidos) == (3, 0, 0, 3)
    assert Movimiento.objects.count() == 3


def test_un_fichero_que_se_solapa_solo_anade_lo_nuevo(perfil):
    extracto.importar_extracto(perfil, "a.csv", CSV.encode())
    mas = CSV + "30/10/2026;TPV VENTAS TARJETAS 30/10;500,00;5.609,16\n"
    r = extracto.importar_extracto(perfil, "b.csv", mas.encode())
    assert (r.nuevos, r.repetidos, Movimiento.objects.count()) == (1, 3, 4)


def test_dos_cobros_identicos_el_mismo_dia_se_guardan_los_dos_y_no_se_duplican_al_reimportar(perfil):
    doble = CSV + "28/10/2026;TRANSF A DISTRIBUCIONES EJEMPLO SL FRA F26-00001;-12,69;5.109,16\n"
    assert extracto.importar_extracto(perfil, "a.csv", doble.encode()).nuevos == 4
    assert extracto.importar_extracto(perfil, "a.csv", doble.encode()).nuevos == 0
    assert Movimiento.objects.filter(importe=D("-12.69")).count() == 2


def test_las_filas_con_error_no_impiden_guardar_las_buenas(perfil):
    r = extracto.importar_extracto(perfil, "a.csv", (CSV + "xx;MAL;1,00;1,00\n").encode())
    assert (r.nuevos, len(r.errores)) == (3, 1)


def test_un_fichero_enorme_se_rechaza(perfil):
    with pytest.raises(extracto.ExtractoNoValido):
        extracto.importar_extracto(perfil, "a.csv", b"x" * (extracto.MAX_BYTES + 1))
