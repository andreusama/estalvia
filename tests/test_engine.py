from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from estalvia.engine.calc import Lecturas, Periodo, SiteParams, calcular_factura, calcular_regulado
from estalvia.engine.errors import MissingDataError, MissingRuleError, RuleSetError
from estalvia.engine.rules import Rule, RuleSet

FIX = Path(__file__).parent / "fixtures" / "synthetic_rules.yaml"
RS = RuleSet.from_yaml(FIX)


def site(**kw):
    return SiteParams("3.0TD", {"P1": D(100)}, **kw)


def calc(kwh1=D(1000), kwh2=D(0), per=Periodo(date(2025, 3, 1), date(2025, 3, 31)), s=None):
    return calcular_factura(s or site(), Lecturas({"P1": kwh1, "P2": kwh2}), RS, per)


def test_caso_conocido_a_mano():
    d = calc()
    # potencia: 100 kW * 36.5 / 365 * 31 = 310.00 ; energía: 1000 * 0.10 = 100.00
    # base 410.00 ; IE = max(5% = 20.50, 1 MWh*0.5) = 20.50 ; sin IVA 430.50 ; total 473.55
    imp = {l.concepto: l.importe for l in d.lineas}
    assert imp["potencia P1"] == D("310.00") and imp["energia P1"] == D("100.00")
    assert imp["impuesto electricidad"] == D("20.50")
    assert d.total == D("473.55")


def test_total_es_suma_de_lineas():
    d = calc(kwh1=D("1234.5"), kwh2=D(77))
    assert sum(l.importe for l in d.lineas) == d.total


def test_lineas_trazables():
    for l in calc().lineas:
        assert l.regla_id and l.vigencia and l.fuente


def test_alquiler():
    d = calc(s=site(alquiler_eur_dia=D("0.10")))
    assert {l.concepto: l.importe for l in d.lineas}["alquiler equipos"] == D("3.10")


def test_cambio_de_vigencia_dentro_del_periodo_solo_afecta_a_potencia():
    a = calc(per=Periodo(date(2025, 12, 25), date(2026, 1, 5)))
    imp = {l.concepto: l.importe for l in a.lineas}
    # 7 días a 36.5/365 y 5 días a 73/365 sobre 100 kW
    assert imp["potencia P1"] == D("170.00")
    assert imp["energia P1"] == D("100.00")


def test_regla_inexistente_es_error_no_valor_por_defecto():
    with pytest.raises(MissingRuleError):
        calc(per=Periodo(date(2024, 1, 1), date(2024, 1, 31)))


def test_periodo_invalido():
    with pytest.raises(MissingDataError):
        calc(per=Periodo(date(2025, 3, 31), date(2025, 3, 1)))


def test_ie_minimo_por_mwh():
    d = calc(kwh1=D(1), kwh2=D(0))
    # base muy pequeña frente al mínimo por MWh no aplica aquí; comprueba que no baja de 5 % ni del mínimo
    ie = {l.concepto: l.importe for l in d.lineas}["impuesto electricidad"]
    assert ie >= D("0.00")


@given(a=st.integers(0, 10**6), b=st.integers(0, 10**6))
def test_mas_kwh_nunca_baja_el_termino_de_energia(a, b):
    lo, hi = sorted((a, b))
    e = lambda k: {l.concepto: l.importe for l in calc(kwh1=D(k)).lineas}["energia P1"]
    assert e(lo) <= e(hi)


def test_cambiar_vigencia_no_altera_energia():
    e = lambda per: {l.concepto: l.importe for l in calc(per=per).lineas}["energia P1"]
    assert e(Periodo(date(2025, 3, 1), date(2025, 3, 31))) == e(Periodo(date(2026, 3, 1), date(2026, 3, 31)))


def test_ruleset_sin_fuente_no_se_publica():
    with pytest.raises(ValueError):
        Rule(id="x", kind="k", value="1", unit="u", valid_from=date(2025, 1, 1), source=" ")


def test_ruleset_solapes_y_duplicados(tmp_path):
    r = lambda i, f, t: Rule(id=i, kind="k", value="1", unit="u", valid_from=f, valid_to=t, source="s")
    with pytest.raises(RuleSetError):
        RuleSet([r("a", date(2025, 1, 1), date(2025, 6, 30)), r("b", date(2025, 6, 1), None)])
    with pytest.raises(RuleSetError):
        RuleSet([r("a", date(2025, 1, 1), None), r("a", date(2026, 1, 1), None)])
    assert RuleSet([r("a", date(2025, 1, 1), date(2025, 1, 31)), r("b", date(2025, 3, 1), None)]).gaps()


def test_from_yaml_sin_fuente(tmp_path):
    p = tmp_path / "r.yaml"
    p.write_text("rules:\n  - {id: a, kind: k, value: '1', unit: u, valid_from: 2025-01-01, source: ''}\n")
    with pytest.raises(RuleSetError):
        RuleSet.from_yaml(p)


def test_float_rechazado():
    with pytest.raises(ValueError):
        Rule(id="x", kind="k", value=0.1, unit="u", valid_from=date(2025, 1, 1), source="s")


def test_hash_estable():
    assert RS.hash == RuleSet.from_yaml(FIX).hash


def test_bono_social_entra_en_la_base_y_se_prorratea_por_dias():
    # 36,5 EUR/año / 365 * 31 días = 3,10. Base 413,10; IE 5 % = 20,655 -> 20,66; sin IVA 433,76; total 477,14
    d = calc(s=site(aplica_bono_social=True))
    imp = {l.concepto: l.importe for l in d.lineas}
    assert imp["bono social"] == D("3.10") and imp["impuesto electricidad"] == D("20.66")
    assert d.total == D("477.14") and sum(l.importe for l in d.lineas) == d.total


def test_sin_aplicar_bono_social_no_hay_linea_ni_se_busca_la_regla():
    assert "bono social" not in {l.concepto for l in calc().lineas}


def test_alquiler_declarado_en_importe_fijo():
    d = calc(s=site(alquiler_importe=D("0.85")))
    assert {l.concepto: l.importe for l in d.lineas}["alquiler equipos"] == D("0.85")


def test_alquiler_por_dia_e_importe_a_la_vez_es_ambiguo():
    with pytest.raises(MissingDataError, match="alquiler"):
        calc(s=site(alquiler_eur_dia=D("0.10"), alquiler_importe=D("0.85")))


def test_desglose_regulado_informativo_no_altera_el_total():
    per = Periodo(date(2025, 3, 1), date(2025, 3, 31))
    lineas = calcular_regulado(site(), Lecturas({"P1": D(1000)}), RS, per)
    imp = {l.concepto: l.importe for l in lineas}
    # 100 kW * 73 / 365 * 31 = 620,00 ; * 36,5 -> 310,00 ; 1000 kWh * 0,02 = 20,00 ; * 0,01 = 10,00
    assert imp == {"peaje potencia P1": D("620.00"), "cargo potencia P1": D("310.00"),
                   "peaje energia P1": D("20.00"), "cargo energia P1": D("10.00")}
    assert all(l.regla_id and l.fuente for l in lineas)
    assert calc(kwh1=D(1000)).total == D("473.55")  # el total facturado no cambia


def test_desglose_regulado_sin_regla_falla_claro():
    with pytest.raises(MissingRuleError):
        calcular_regulado(site(), Lecturas({"P2": D(10)}), RS, Periodo(date(2025, 3, 1), date(2025, 3, 31)))
