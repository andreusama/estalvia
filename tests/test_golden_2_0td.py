"""Factura de referencia 2.0TD: el motor frente a los importes impresos en una factura real.

Los datos de la factura NO están en el repositorio: viven en `tests/golden/private/` (ignorado por git).
Sin ese fichero los tests se omiten, y la cobertura de 2.0TD en CI la da `test_2_0td_sintetico.py`.

Desviación conocida: las líneas de energía de la factura no salen de su precio impreso con redondeo por
línea (unos céntimos en dos líneas). La comercializadora redondea o arrastra decimales de forma que no se
ve en la factura; no se supone ninguna regla. El detalle y los valores del motor están en el fichero local.
Si el motor cambia esos valores, hay que explicarlo por escrito y aprobarlo (TDD sección 14, regla 5).
"""
from datetime import date
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from estalvia.engine.calc import Lecturas, Periodo, SiteParams, calcular_factura, calcular_regulado
from estalvia.engine.rules import Rule, RuleSet

RAIZ = Path(__file__).parents[1]
FIXTURE = RAIZ / "tests/golden/private/2_0td_2026_09.yaml"


@pytest.fixture(scope="module")
def ref():
    if not FIXTURE.exists():
        pytest.skip("factura de referencia local no disponible (tests/golden/private/)")
    g = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    reales = [r for f in sorted((RAIZ / "rules").glob("*.yaml")) for r in RuleSet.from_yaml(f).rules]
    c, src = g["contrato"], "contrato de la factura de referencia (local)"
    contrato = [Rule(id=f"CONTRATO-POT-{p}", kind="potencia_eur_kw_anio", tariff=g["tarifa"], period=p,
                     value=c["potencia_eur_kw_anio"], unit="EUR/kW/año", valid_from=date(2026, 1, 1), source=src)
                for p in g["potencia_contratada_kw"]]
    contrato += [Rule(id=f"CONTRATO-ENE-{p}", kind="energia_eur_kwh", tariff=g["tarifa"], period=p,
                      value=c["energia_eur_kwh"], unit="EUR/kWh", valid_from=date(2026, 1, 1), source=src)
                 for p in g["energia_kwh"]]
    return SimpleNamespace(
        g=g, f=g["factura"], rs=RuleSet(reales + contrato),
        site=SiteParams(g["tarifa"], {p: D(v) for p, v in g["potencia_contratada_kw"].items()},
                        alquiler_importe=D(g["alquiler_importe"]), ie_uso=g["ie_uso"],
                        aplica_bono_social=g["aplica_bono_social"]),
        lec=Lecturas({p: D(v) for p, v in g["energia_kwh"].items()}),
        per=Periodo(g["periodo"]["inicio"], g["periodo"]["fin"]))


def _lineas(r):
    return {x.concepto: x.importe for x in calcular_factura(r.site, r.lec, r.rs, r.per).lineas}


def test_potencia_bono_ie_alquiler_e_iva_coinciden_exactamente(ref):
    f, lineas = ref.f, _lineas(ref)
    assert lineas["potencia P1"] == D(f["potencia"]["P1"]) and lineas["potencia P2"] == D(f["potencia"]["P2"])
    assert lineas["bono social"] == D(f["bono_social"])
    assert lineas["impuesto electricidad"] == D(f["impuesto_electricidad"])
    assert lineas["alquiler equipos"] == D(f["alquiler"]) and lineas["iva"] == D(f["iva"])


def test_energia_dentro_de_un_centimo_por_linea_con_la_desviacion_conocida(ref):
    lineas = _lineas(ref)
    for p in ref.g["energia_kwh"]:
        assert abs(lineas[f"energia {p}"] - D(ref.f["energia"][p])) <= D("0.01")
    assert {p: lineas[f"energia {p}"] for p in ref.g["energia_kwh"]} == {
        p: D(v) for p, v in ref.g["motor_actual"]["energia"].items()}


def test_total_dentro_de_dos_centimos_y_muy_por_debajo_del_umbral_del_tdd(ref):
    total = calcular_factura(ref.site, ref.lec, ref.rs, ref.per).total
    assert total == D(ref.g["motor_actual"]["total"])
    assert abs(total - D(ref.f["total"])) <= D("0.02")
    assert abs(total - D(ref.f["total"])) / D(ref.f["total"]) <= D("0.005")  # umbral del TDD: 0,5 %


def test_el_total_es_la_suma_de_las_lineas(ref):
    desglose = calcular_factura(ref.site, ref.lec, ref.rs, ref.per)
    assert sum(x.importe for x in desglose.lineas) == desglose.total


def test_desglose_regulado_coincide_al_centimo_con_la_factura(ref):
    regulado = {x.concepto: x.importe for x in calcular_regulado(ref.site, ref.lec, ref.rs, ref.per)}
    assert regulado == {k: D(v) for k, v in ref.f["regulado"].items()}
