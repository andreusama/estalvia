from decimal import Decimal as D

from estalvia.ai.masking import enmascarar
from estalvia.extraction.schema import FacturaExtraida, validar_factura
from estalvia.reports.figure_checker import cifras_inexistentes


def factura(total="121.00", ini="2025-03-01", fin="2025-03-31", cups="ES0000000000000000AA"):
    return FacturaExtraida.model_validate({
        "comercializadora": "X", "cups": cups, "tarifa_acceso": "3.0TD",
        "modalidad_precio": "fijo", "periodo_facturado": {"inicio": ini, "fin": fin},
        "potencia_contratada_kw": {"P1": "50"}, "energia_kwh": {"P1": "100"},
        "conceptos": [{"nombre": "energia", "cantidad": "100", "precio": "1", "importe": "100"}],
        "impuestos": {"electrico": "5", "iva": "16"},
        "total": total,
    })


def test_factura_cuadra():
    assert validar_factura(factura()) == []


def test_factura_no_cuadra_y_solape():
    assert validar_factura(factura(total="130"))
    assert validar_factura(factura(ini="2025-03-15", fin="2025-04-15"), [factura()])
    assert not validar_factura(factura(ini="2025-04-01", fin="2025-04-30"), [factura()])


def test_enmascarado():
    t = enmascarar("Titular Juan Pérez NIF 12345678Z CUPS ES0021000000000000AB dir Calle Sol 5",
                   ["Juan Pérez", "Calle Sol 5"], clave=b"clave-de-prueba")
    assert "12345678Z" not in t and "Juan" not in t and "Calle Sol" not in t
    assert "0021000000000000" not in t


def test_comprobador_de_cifras():
    datos = {D("1234.5"), D(12)}
    assert cifras_inexistentes("Ahorras 1.234,5 € en 12 meses", datos) == []
    assert cifras_inexistentes("Ahorras 999 €", datos) == [D(999)]
