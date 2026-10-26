"""Esquema de extracción y comprobaciones deterministas (spec #10, ticket #11). Solo datos sintéticos."""
from decimal import Decimal

import pytest
from pydantic import ValidationError

from estalvia.extraction.schema import FacturaExtraida, validar_datos, validar_factura


def datos(**cambios):
    base = {
        "comercializadora": "X", "cups": "ES0000000000000000AA", "tarifa_acceso": "2.0TD",
        "modalidad_precio": "fijo", "periodo_facturado": {"inicio": "2026-01-01", "fin": "2026-01-31"},
        "potencia_contratada_kw": {"P1": "4.4", "P2": "4.4"},
        "energia_kwh": {"P1": "50", "P2": "60", "P3": "90"},
        "conceptos": [{"nombre": "energia", "cantidad": "200", "precio": "0.5", "importe": "100"}],
        "impuestos": {"electrico": "5", "iva": "22.05"},
        "total": "127.05",
    }
    base.update(cambios)
    return base


def factura(**cambios):
    return FacturaExtraida.model_validate(datos(**cambios))


def test_factura_2_0td_cuadra():
    assert validar_factura(factura()) == []


def test_2_0td_solo_admite_tres_periodos_de_energia():
    with pytest.raises(ValidationError, match="P4"):
        factura(energia_kwh={"P1": "1", "P4": "1"})


def test_2_0td_admite_la_potencia_contratada_en_seis_periodos_porque_las_facturas_la_imprimen_asi():
    f = factura(potencia_contratada_kw={p: "4.4" for p in ("P1", "P2", "P3", "P4", "P5", "P6")})
    assert set(f.potencia_contratada_kw) == {"P1", "P2", "P3", "P4", "P5", "P6"} and validar_factura(f) == []


def test_lecturas_del_contador_son_opcionales_y_no_se_inventan():
    assert factura().lecturas_contador is None
    assert factura().desglose_regulado is None


def test_lecturas_del_contador_se_representan_por_periodo():
    f = factura(lecturas_contador={"P1": {"inicial": "1000", "final": "1050"}})
    assert f.lecturas_contador["P1"].final == 1050


def test_lectura_final_menor_que_la_inicial_se_rechaza():
    with pytest.raises(ValidationError, match="final"):
        factura(lecturas_contador={"P1": {"inicial": "1050", "final": "1000"}})


def test_desglose_regulado_se_representa():
    f = factura(desglose_regulado=[{"nombre": "peajes", "importe": "12.34"}])
    assert f.desglose_regulado[0].importe == Decimal("12.34")


def test_diferencia_de_suma_de_dos_centimos_pasa():
    assert validar_factura(factura(total="127.07")) == []
    assert validar_factura(factura(total="127.03")) == []


def test_diferencia_mayor_de_dos_centimos_falla_y_nombra_ambas_cifras():
    problemas = validar_factura(factura(total="127.08"))
    assert len(problemas) == 1
    assert "127.05" in problemas[0] and "127.08" in problemas[0]


def test_solape_con_otra_factura_del_mismo_cups_falla():
    otra = factura(periodo_facturado={"inicio": "2026-01-20", "fin": "2026-02-19"})
    assert any("solapa" in p for p in validar_factura(factura(), [otra]))


def test_otro_cups_no_solapa():
    otra = factura(cups="ES1111111111111111BB")
    assert validar_factura(factura(), [otra]) == []


def test_kwh_negativos_fallan():
    problemas = validar_factura(factura(energia_kwh={"P1": "-1", "P2": "60", "P3": "90"}))
    assert any("negativos" in p for p in problemas)


@pytest.mark.parametrize("campo", ["potencia_contratada_kw", "energia_kwh"])
def test_campo_critico_ausente_es_un_problema_no_un_valor_por_defecto(campo):
    d = datos()
    del d[campo]
    problemas = validar_factura(FacturaExtraida.model_validate(d))
    assert any(campo in p for p in problemas)


def test_sin_conceptos_es_un_problema():
    problemas = validar_factura(factura(conceptos=[]))
    assert any("conceptos" in p for p in problemas)


def test_datos_validos_dan_factura_y_sin_problemas():
    f, problemas = validar_datos(datos())
    assert f is not None and problemas == []


@pytest.mark.parametrize("campo", ["total", "periodo_facturado"])
def test_total_o_fechas_ausentes_van_a_revision_sin_excepcion(campo):
    d = datos()
    del d[campo]
    f, problemas = validar_datos(d)
    assert f is None
    assert any(campo in p for p in problemas)


def test_periodo_no_valido_para_la_tarifa_va_a_revision():
    f, problemas = validar_datos(datos(energia_kwh={"P1": "1", "P4": "1"}))
    assert f is None and any("P4" in p for p in problemas)


def test_lecturas_del_contador_se_aceptan_en_seis_periodos_como_las_imprime_la_factura_y_P7_no_existe():
    f = factura(lecturas_contador={p: {"inicial": "1", "final": "2"} for p in ("P1", "P2", "P3", "P4", "P5", "P6")})
    assert len(f.lecturas_contador) == 6
    with pytest.raises(ValidationError, match="P7"):
        factura(lecturas_contador={"P7": {"inicial": "1", "final": "2"}})


def test_nulos_explicitos_se_conservan_como_ausentes():
    f = factura(lecturas_contador=None, desglose_regulado=None)
    assert f.lecturas_contador is None and f.desglose_regulado is None


def test_los_problemas_no_incluyen_valores_de_la_factura_en_errores_de_esquema():
    _, problemas = validar_datos(datos(total="no-es-un-numero"))
    assert problemas and "no-es-un-numero" not in " ".join(problemas)


def test_un_concepto_solo_con_nombre_e_importe_es_valido_cantidad_y_precio_son_opcionales():
    f = factura(conceptos=[{"nombre": "alquiler de equipos", "importe": "100"}])
    assert f.conceptos[0].cantidad is None and f.conceptos[0].precio is None
    assert validar_factura(f) == []


def test_un_concepto_sin_importe_sigue_siendo_invalido():
    f, problemas = validar_datos(datos(conceptos=[{"nombre": "energia", "cantidad": "1", "precio": "1"}]))
    assert f is None and any("importe" in p for p in problemas)
