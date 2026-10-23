"""2.0TD con consumo SINTÉTICO y las reglas reales del BOE (peajes y cargos 2026, segmento 1).
Los importes esperados están calculados a mano con los valores de las tablas del BOE."""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from estalvia.engine.calc import Lecturas, Periodo, SiteParams, calcular_regulado
from estalvia.engine.rules import RuleSet

R = Path(__file__).parents[1] / "rules"
RS = RuleSet([r for f in sorted(R.glob("*.yaml")) for r in RuleSet.from_yaml(f).rules])


def test_desglose_regulado_2_0td_sintetico_calculado_a_mano():
    # 5 kW en P1 y P2, 30 días (1-30 jun 2026, año de 365 días); 100 kWh en cada periodo.
    # Potencia peaje P1: 5 x 23,324952 / 365 x 30 = 9,5856 -> 9,59 ; P2: 5 x 0,443770 / 365 x 30 = 0,1824 -> 0,18
    # Potencia cargo P1: 5 x 4,379461 / 365 x 30 = 1,7998 -> 1,80 ; P2: 5 x 0,281653 / 365 x 30 = 0,1158 -> 0,12
    # Energía peaje: 100 x 0,033261 = 3,33 ; 100 x 0,016409 = 1,64 ; 100 x 0,000077 = 0,0077 -> 0,01
    # Energía cargo: 100 x 0,064292 = 6,43 ; 100 x 0,012858 = 1,29 ; 100 x 0,003215 = 0,3215 -> 0,32
    site = SiteParams("2.0TD", {"P1": D(5), "P2": D(5)})
    lec = Lecturas({"P1": D(100), "P2": D(100), "P3": D(100)})
    lineas = calcular_regulado(site, lec, RS, Periodo(date(2026, 6, 1), date(2026, 6, 30)))
    assert {x.concepto: x.importe for x in lineas} == {
        "peaje potencia P1": D("9.59"), "peaje potencia P2": D("0.18"),
        "cargo potencia P1": D("1.80"), "cargo potencia P2": D("0.12"),
        "peaje energia P1": D("3.33"), "peaje energia P2": D("1.64"), "peaje energia P3": D("0.01"),
        "cargo energia P1": D("6.43"), "cargo energia P2": D("1.29"), "cargo energia P3": D("0.32")}
