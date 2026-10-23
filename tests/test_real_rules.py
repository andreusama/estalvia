"""Comprobaciones de los RuleSet reales (rules/) contra fuentes independientes de las tablas del BOE."""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from estalvia.engine.calc import Lecturas, Periodo, SiteParams, calcular_factura  # noqa: F401
from estalvia.engine.errors import MissingRuleError
from estalvia.engine.periods import Calendario
from estalvia.engine.rules import RuleSet

R = Path(__file__).parents[1] / "rules"
RS = RuleSet([r for f in sorted(R.glob("*.yaml")) for r in RuleSet.from_yaml(f).rules])
CAL = Calendario.desde_directorio(R / "calendar")
D26 = date(2026, 6, 15)


def total(kind_a, kind_b, tar, p, d=D26):
    return RS.find(kind_a, d, tar, p).value + RS.find(kind_b, d, tar, p).value


# Totales peaje + cargo publicados por una comercializadora (fuente independiente del BOE).
@pytest.mark.parametrize("tar,p,esperado", [
    ("3.0TD", "P1", "20.376927"), ("6.1TD", "P1", "29.595368"),
    ("3.0TD", "P2", "10.617621"), ("6.1TD", "P2", "15.514709"),
])
def test_potencia_peaje_mas_cargo_2026(tar, p, esperado):
    assert total("peaje_potencia_eur_kw_anio", "cargo_potencia_eur_kw_anio", tar, p) == D(esperado)


@pytest.mark.parametrize("tar,esperado", [("3.0TD", "0.063352"), ("6.1TD", "0.046274")])
def test_energia_p1_peaje_mas_cargo_2026(tar, esperado):
    assert total("peaje_energia_eur_kwh", "cargo_energia_eur_kwh", tar, "P1") == D(esperado)


def test_peaje_2025_vs_2026_distintos():
    a = RS.find("peaje_potencia_eur_kw_anio", date(2025, 6, 1), "3.0TD", "P1")
    b = RS.find("peaje_potencia_eur_kw_anio", date(2026, 6, 1), "3.0TD", "P1")
    assert (a.value, b.value) == (D("14.723431"), D("14.935084"))


def test_todas_las_reglas_tienen_fuente_y_ninguna_es_2024():
    assert all(r.source for r in RS.rules)
    with pytest.raises(MissingRuleError):
        RS.find("peaje_potencia_eur_kw_anio", date(2024, 12, 31), "3.0TD", "P1")


def test_iee_cronologia_2026():
    ie = lambda d: RS.find("ie_pct", d).value  # noqa: E731
    assert ie(date(2026, 3, 21)) == D("5.11269632")
    assert ie(date(2026, 3, 22)) == D("0.5")
    assert ie(date(2026, 5, 31)) == D("0.5")
    assert ie(date(2026, 6, 1)) == D("5.11269632")


def test_iva_general_para_mas_de_10kw():
    assert RS.find("iva_pct", date(2026, 4, 1)).value == D("21")


def test_reactiva_y_excesos_2026_presentes():
    assert RS.find("reactiva_inductiva_cosphi_lt_080_eur_kvarh", D26).value == D("0.0623320")
    assert RS.find("exceso_potencia_tepp45_eur_kw_dia", D26, "6.1TD", "P1").value == D("0.275735")


# --- Periodos horarios y Cataluña ---
def test_periodos_tipo_dia():
    assert CAL.periodo(date(2026, 1, 14), 10) == "P1"  # miércoles de enero (A)
    assert CAL.periodo(date(2026, 1, 14), 3) == "P6"
    assert CAL.periodo(date(2026, 5, 13), 10) == "P4"  # temporada baja (C)
    assert CAL.periodo(date(2026, 5, 13), 22) == "P5"
    assert CAL.periodo(date(2026, 5, 16), 12) == "P6"  # sábado


def test_cataluna_no_cambia_los_periodos():
    # 11-sep-2026 (Diada) es viernes laborable a efectos tarifarios: temporada media -> B1
    assert CAL.tipo_dia(date(2026, 9, 11)) == "B1" and CAL.periodo(date(2026, 9, 11), 10) == "P3"
    # Lunes de Pascua (festivo en Cataluña) también es laborable tarifario
    assert CAL.tipo_dia(date(2026, 4, 6)) == "C"
    # Viernes Santo: sin fecha fija, excluido por el art. 7.2.b
    assert CAL.tipo_dia(date(2026, 4, 3)) == "C"
    # festivos nacionales de fecha fija sí
    assert CAL.tipo_dia(date(2026, 12, 8)) == "D" and CAL.tipo_dia(date(2026, 1, 6)) == "D"


def test_ie_min_por_uso_en_motor():
    sp = SiteParams("3.0TD", {"P1": D(100)}, ie_uso="profesional")
    # con reglas reales faltaría la regla de energía contratada: debe fallar claro, sin valor por defecto
    with pytest.raises(MissingRuleError):
        calcular_factura(sp, Lecturas({"P1": D(10)}), RS, Periodo(date(2026, 6, 1), date(2026, 6, 30)))


# --- 2.0TD: 3 periodos de energía y 2 de potencia (Circular 3/2020 art. 7.3 y 7.4) ---
def test_2_0td_energia_tres_periodos():
    jueves = date(2026, 9, 10)
    assert [CAL.periodo_energia_2_0td(jueves, h) for h in (3, 7, 8, 9, 10, 13, 14, 17, 18, 21, 22, 23)] == [
        "P3", "P3", "P2", "P2", "P1", "P1", "P2", "P2", "P1", "P1", "P2", "P2"]


def test_2_0td_fines_de_semana_y_festivos_nacionales_son_valle():
    assert {CAL.periodo_energia_2_0td(date(2026, 9, 12), h) for h in range(24)} == {"P3"}  # sábado
    assert {CAL.periodo_energia_2_0td(date(2026, 10, 12), h) for h in range(24)} == {"P3"}  # lunes festivo
    # festivo solo catalán (Diada, viernes): día normal
    assert CAL.periodo_energia_2_0td(date(2026, 9, 11), 10) == "P1"


def test_2_0td_potencia_punta_es_p1_mas_p2_y_valle_es_p3():
    jueves = date(2026, 9, 10)
    assert [CAL.periodo_potencia_2_0td(jueves, h) for h in (3, 7, 8, 10, 23)] == ["P2", "P2", "P1", "P1", "P1"]
    assert CAL.periodo_potencia_2_0td(date(2026, 9, 12), 12) == "P2"


def test_2_0td_reglas_cargadas_con_los_periodos_que_existen():
    assert RS.find("peaje_potencia_eur_kw_anio", D26, "2.0TD", "P1").value == D("23.324952")
    assert RS.find("cargo_energia_eur_kwh", D26, "2.0TD", "P3").value == D("0.003215")
    with pytest.raises(MissingRuleError):  # 2.0TD no tiene P3 de potencia
        RS.find("peaje_potencia_eur_kw_anio", D26, "2.0TD", "P3")


def test_bono_social_solo_desde_julio_2026_y_falla_antes():
    assert RS.find("bono_social_eur_cups_anio", date(2026, 9, 15)).value == D("9.011295")
    with pytest.raises(MissingRuleError):
        RS.find("bono_social_eur_cups_anio", date(2026, 6, 30))


def test_2_0td_no_tiene_periodos_p4_a_p6_de_energia_ni_p3_a_p6_de_potencia():
    for p in ("P4", "P5", "P6"):
        for kind in ("peaje_energia_eur_kwh", "cargo_energia_eur_kwh"):
            with pytest.raises(MissingRuleError):
                RS.find(kind, D26, "2.0TD", p)
    for p in ("P3", "P4", "P5", "P6"):
        with pytest.raises(MissingRuleError):
            RS.find("cargo_potencia_eur_kw_anio", D26, "2.0TD", p)
