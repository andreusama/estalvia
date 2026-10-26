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
