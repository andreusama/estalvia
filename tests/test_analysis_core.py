"""Núcleo del análisis (spec #18, ticket #19): línea base y escenario de una 2.0TD con datos SINTÉTICOS.
Un domingo entero es P3 (2.0TD), así que los importes se calculan a mano:
  potencia: 4 kW x 30 EUR/kW/año / 365 = 0,3288 -> 0,33 (P1) ; 4 kW x 3 / 365 = 0,0329 -> 0,03 (P2)
  energía: 24 kWh x 0,10 = 2,40 ; base 2,76 ; IE 5,11269632 % = 0,1411 -> 0,14 ; sin IVA 2,90 ; total 3,51
  escenario con 12 kWh: energía 1,20 ; base 1,56 ; IE 0,0798 -> 0,08 ; sin IVA 1,64 ; total 1,98 ; ahorro 1,53"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest

from estalvia.analysis.nucleo import FaltaDato, PrecioContrato, comparar, linea_base
from estalvia.engine.calc import Periodo, SiteParams
from estalvia.engine.periods import Calendario
from estalvia.engine.rules import RuleSet
from estalvia.ingestion.hourly import ingest_hourly

RAIZ = Path(__file__).parents[1]
REGLAS = RuleSet([r for f in sorted((RAIZ / "rules").glob("*.yaml")) for r in RuleSet.from_yaml(f).rules])
CALENDARIO = Calendario.desde_directorio(RAIZ / "rules/calendar")
DOMINGO = Periodo(date(2026, 6, 7), date(2026, 6, 7))
SITIO = SiteParams("2.0TD", {"P1": D(4), "P2": D(4)})
PRECIOS = PrecioContrato(energia_eur_kwh={"P1": D("0.20"), "P2": D("0.15"), "P3": D("0.10")},
                         potencia_eur_kw_anio={"P1": D(30), "P2": D(3)})


def consumo_del_domingo(kwh_por_hora: str = "1", horas=range(24)):
    filas = "".join(f"2026-06-07T{h:02d}:00:00+02:00,{kwh_por_hora},0,real\n" for h in horas)
    return ingest_hourly(("instante,kwh,kvarh,tipo\n" + filas).encode(), "interno")


def base(ingesta, precios=PRECIOS):
    return linea_base(SITIO, ingesta, CALENDARIO, REGLAS, precios, DOMINGO)


def test_la_linea_base_coincide_con_el_calculo_a_mano():
    d = base(consumo_del_domingo())
    assert d.total == D("3.51")
    assert {x.concepto: x.importe for x in d.lineas}["energia P3"] == D("2.40")


def test_sin_precio_de_un_periodo_consumido_falta_el_dato_y_no_se_estima():
    sin_p3 = PrecioContrato(energia_eur_kwh={"P1": D("0.20"), "P2": D("0.15")},
                            potencia_eur_kw_anio=PRECIOS.potencia_eur_kw_anio)
    with pytest.raises(FaltaDato, match="precio.*P3"):
        base(consumo_del_domingo(), sin_p3)


def test_consumo_incompleto_en_el_periodo_facturado_falta_el_dato():
    with pytest.raises(FaltaDato, match="consumo"):
        base(consumo_del_domingo(horas=range(23)))


def test_el_ahorro_es_la_diferencia_entre_linea_base_y_escenario():
    c = comparar(SITIO, consumo_del_domingo(), consumo_del_domingo("0.5"), CALENDARIO, REGLAS, PRECIOS, DOMINGO)
    assert (c.base.total, c.escenario.total, c.ahorro) == (D("3.51"), D("1.98"), D("1.53"))
    assert comparar(SITIO, consumo_del_domingo(), consumo_del_domingo(), CALENDARIO, REGLAS, PRECIOS,
                    DOMINGO).ahorro == D(0)


def test_un_dia_de_25_horas_por_cambio_de_hora_se_calcula_con_sus_25_horas():
    # 2026-10-25 (domingo, 25 h): 25 kWh en P3 = 2,50 ; base 2,86 ; IE 0,1462 -> 0,15 ; sin IVA 3,01 ; total 3,64
    inicio = datetime(2026, 10, 24, 22, 0, tzinfo=timezone.utc)
    filas = "".join(f"{(inicio + timedelta(hours=h)).isoformat()},1,0,real\n" for h in range(25))
    ingesta = ingest_hourly(("instante,kwh,kvarh,tipo\n" + filas).encode(), "interno")
    dia = Periodo(date(2026, 10, 25), date(2026, 10, 25))
    assert linea_base(SITIO, ingesta, CALENDARIO, REGLAS, PRECIOS, dia).total == D("3.64")


def test_sin_precio_de_potencia_falta_el_dato():
    sin_potencia = PrecioContrato(energia_eur_kwh=PRECIOS.energia_eur_kwh, potencia_eur_kw_anio={"P1": D(30)})
    with pytest.raises(FaltaDato, match="precio de potencia.*P2"):
        base(consumo_del_domingo(), sin_potencia)


def test_un_consumo_negativo_no_se_calcula():
    with pytest.raises(FaltaDato, match="negativo"):
        base(consumo_del_domingo("-1"))
