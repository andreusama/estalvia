"""Enmascarado antes de enviar texto a la IA (spec #10, ticket #12). Solo datos sintéticos."""
import pytest

from estalvia.ai.masking import enmascarar, token_cups

CLAVE = b"clave-de-prueba-no-real"
CUPS = "ES0000000000000000AA"

FACTURA_ES = """\
Titular: Ana Ejemplo Prueba
NIF: 00000000T
Dirección de suministro: Calle Inventada 12, 3º B
Código postal: 99999   Población: Villaficticia
Teléfono: 600000000   Email: ana@ejemplo.invalid
Contrato de acceso nº 0000111122   Nº de factura: FE-2026-000123
IBAN: ES00 0000 0000 0000 0000 0000
CUPS: ES0000000000000000AA
Periodo facturado: 01/09/2026 a 02/10/2026
Potencia contratada P1: 4,400 kW
Energía P1 (punta): 31,25 kWh x 0,150000 €/kWh = 4,69 €
Total factura: 55,95 €
"""

FACTURA_CA = """\
Titular: Joan Exemple Proves
Adreça de subministrament: Carrer Inventat 7, 2n 1a
Codi postal: 99999   Població: Vilaficticia
Telèfon: 600000000
Contracte d'accés núm. 0000333344   Número de factura: FC-2026-000456
CUPS: ES0000000000000000AA
Període facturat: 01/09/2026 a 02/10/2026
Potència contractada P1: 4,400 kW
Total factura: 55,95 €
"""

PERSONALES = ["Ana", "Ejemplo", "Joan", "Proves", "00000000T", "Inventada", "Inventat", "99999", "Villaficticia",
              "Vilaficticia", "600000000", "ana@ejemplo", "0000111122", "FE-2026-000123", "0000333344",
              "FC-2026-000456", "ES00 0000 0000", "ES0000000000000000AA"]


@pytest.mark.parametrize("texto", [FACTURA_ES, FACTURA_CA])
def test_campos_personales_etiquetados_desaparecen(texto):
    salida = enmascarar(texto, clave=CLAVE)
    for dato in PERSONALES:
        assert dato not in salida, dato


@pytest.mark.parametrize("texto", [FACTURA_ES, FACTURA_CA])
def test_las_cifras_de_calculo_no_se_alteran(texto):
    salida = enmascarar(texto, clave=CLAVE)
    for linea in texto.splitlines():
        if linea.startswith(("Periodo facturado", "Període facturat", "Potencia", "Potència", "Energía",
                             "Total")):
            assert linea in salida.splitlines(), linea


def test_extra_enmascara_valores_conocidos_donde_aparezcan():
    salida = enmascarar("Hola Ana Ejemplo Prueba, su casa", ["Ana Ejemplo Prueba"], clave=CLAVE)
    assert "Ana" not in salida


def test_cups_da_un_token_estable_y_sin_rastro_del_cups():
    a = enmascarar(f"CUPS: {CUPS}", clave=CLAVE)
    b = enmascarar(f"otro texto {CUPS}", clave=CLAVE)
    token = token_cups(CUPS, CLAVE)
    assert token in a and token in b
    assert "000000" not in token and CUPS[:4] not in token


def test_cups_distintos_o_claves_distintas_dan_tokens_distintos():
    otro = "ES1111111111111111BB"
    assert token_cups(CUPS, CLAVE) != token_cups(otro, CLAVE)
    assert token_cups(CUPS, CLAVE) != token_cups(CUPS, b"otra-clave")


def test_cups_con_sufijo_y_en_minusculas_se_reconoce_como_el_mismo():
    assert token_cups(CUPS.lower(), CLAVE) == token_cups(CUPS, CLAVE)
    assert "0F" not in enmascarar(f"CUPS {CUPS}0F", clave=CLAVE)


def test_sin_clave_no_hay_token_estable():
    with pytest.raises(ValueError, match="clave"):
        enmascarar(FACTURA_ES, clave=b"")


def test_texto_sin_datos_personales_queda_igual():
    texto = "Energía P2: 10,00 kWh x 0,100000 €/kWh = 1,00 €\n"
    assert enmascarar(texto, clave=CLAVE) == texto


# Líneas de cálculo con palabras de etiqueta dentro (contrato, nombre, nom, factura...): no deben tocarse.
LINEAS_DE_CALCULO = [
    "Potencia según contrato 4,4 kW",
    "Periodo de contrato 01/09/2026 a 02/10/2026",
    "Contrato 2.0TD 4,4 kW 0,1 €/kW día",
    "Contrato de energía  P1: 31,25 kWh x 0,15 = 4,69",
    "Contracte: 31,25 kWh",
    "Nombre comercial P1  4,4 kW",
    "nom   Energia P1 31,25 kWh",
    "Nombre de la tarifa: 2.0TD",
    "Fecha de contrato: 01/01/2026",
    "Nº de factura anterior: 1",
    "Número de contador   01/09/2026  12345",
    "Importe factura 55,95 €",
]


@pytest.mark.parametrize("linea", LINEAS_DE_CALCULO)
def test_las_lineas_de_calculo_con_palabras_de_etiqueta_no_se_tocan(linea):
    assert enmascarar(linea, clave=CLAVE) == linea


@pytest.mark.parametrize("linea,secreto", [
    ("Cliente: Ana Ejemplo", "Ana"),
    ("Sr. Juan Ejemplo Prueba", "Juan"),
    ("Sra. Marta Ejemplo", "Marta"),
    ("Domicili: Carrer Inventat 7", "Inventat"),
    ("C.P.: 08000", "08000"),
    ("CP: 08000", "08000"),
    ("08000 Villaficticia", "Villaficticia"),
    ("Dirección de envío: Calle Inventada 3", "Inventada"),
    ("Factura: FE-3", "FE-3"),
    ("N.º de factura FE-4", "FE-4"),
    ("Contador: 12345678", "12345678"),
    ("Nº de serie del contador: 998877", "998877"),
    ("Equipo de medida nº 998877", "998877"),
    ("Tel. 93 000 00 00", "93 000 00 00"),
    ("Telf: +34 600000000", "600000000"),
    ("Móvil: 600 00 00 00", "600 00 00 00"),
    ("Fax: 93 000 00 00", "93 000 00 00"),
    ("Referencia catastral: 0000000AA0000A0000AA", "0000000AA"),
    ("DNI 00000000-T", "00000000"),
    ("NIE y1234567l", "1234567"),
    ("IBAN ES00-0000-0000-00-0000000000", "0000000000"),
    ("IBAN ES00 0000 0000 00 0000000000", "0000000000"),
    ("IBAN ES**-****-****-**-******1234", "1234"),
    ("CUPS ES 0000 0000 0000 0000 AA", "0000 0000"),
    ("CUPS ES0000000000000000AA0FP1", "0FP1"),
])
def test_datos_personales_en_otros_formatos_desaparecen(linea, secreto):
    assert secreto not in enmascarar(linea, clave=CLAVE)


def test_cups_con_espacios_da_el_mismo_token_que_sin_espacios():
    con = enmascarar("CUPS ES 0000 0000 0000 0000 AA", clave=CLAVE)
    assert token_cups(CUPS, CLAVE) in con


def test_cups_bajo_etiqueta_conserva_su_token():
    assert token_cups(CUPS, CLAVE) in enmascarar(f"Punto de suministro: {CUPS}", clave=CLAVE)


def test_extra_se_aplica_antes_que_los_patrones_y_tolera_espacios_dobles():
    salida = enmascarar("Dirección: Calle  Sol 5, Madrid", ["Calle Sol 5"], clave=CLAVE)
    assert "Sol" not in salida and "5" not in salida.split(":")[1]


def test_token_cups_sin_clave_falla():
    with pytest.raises(ValueError, match="clave"):
        token_cups(CUPS, b"")


def test_la_clave_debe_ser_bytes():
    with pytest.raises(TypeError, match="bytes"):
        enmascarar("x", clave="texto")


@pytest.mark.parametrize("linea,secreto", [
    ("Número de contracte d’accés: 000011112222", "000011112222"),
    ("Número de contracte d'accés: 000011112222", "000011112222"),
    ("Número de contrato de acceso: 000011112222", "000011112222"),
    ("Contracte d’accés núm. 0000333344", "0000333344"),
    ("Lectures del comptador 123456789", "123456789"),
    ("Lecturas del contador 123456789", "123456789"),
])
def test_contrato_con_apostrofo_tipografico_y_numero_de_contador_se_enmascaran(linea, secreto):
    assert secreto not in enmascarar(linea, clave=CLAVE)


@pytest.mark.parametrize("linea", [
    "Lectures del comptador P1 inicial 1000,5 final 1050,2",
    "Lectures del comptador",
    "Valor 0,123456789 €/dia",
    "Telèfon d’emergències de la distribuïdora: 800 760 909",
])
def test_no_se_enmascaran_las_cifras_de_calculo_ni_los_datos_publicos_cercanos(linea):
    assert enmascarar(linea, clave=CLAVE) == linea


@pytest.mark.parametrize("texto,secreto", [
    ("Adreça de subministrament:\nCalle Inventada 12, 3º B\nSegüent", "Inventada"),
    ("Dirección de suministro:\n\n   Calle Inventada 12", "Inventada"),
    ("CL INVENTADA GRANDE 12 3° 2ª", "INVENTADA"),
    ("Carrer Inventat 7, 2n 1a", "Inventat"),
    ("Avda. Ficticia 3", "Ficticia"),
    ("Plaza Inexistente 4, 1º", "Inexistente"),
    ("Total   31,00 €    08000, VILLAFICTICIA, BARCELONA", "VILLAFICTICIA"),
    ("Total   31,00 €    08000, VILLAFICTICIA, BARCELONA", "BARCELONA"),
    ("Mr.  Mr.    08000, Vilaficticia,", "Vilaficticia"),
])
def test_direcciones_en_la_linea_siguiente_calles_y_codigo_postal_con_coma(texto, secreto):
    assert secreto not in enmascarar(texto, clave=CLAVE)


@pytest.mark.parametrize("texto", [
    "Distribuïdora:\nENDESA DISTRIBUCIÓN ELECTRICA S.L.",
    "Contracte:\n31,25 kWh",
    "Total   31,00 €    kWh 1.234,50",
    "Energia punta   100 x 0,150000   15,00 €",
    "Impost sobre l'electricitat   5,11269632 % s/ 43,00 €   2,20 €",
    "Via de comunicació amb la distribuïdora",
])
def test_estas_lineas_no_son_direcciones_y_no_se_tocan(texto):
    assert enmascarar(texto, clave=CLAVE) == texto


def test_la_cifra_junto_a_un_codigo_postal_se_conserva():
    salida = enmascarar("Total   31,00 €    08000, VILLAFICTICIA, BARCELONA", clave=CLAVE)
    assert "31,00 €" in salida
