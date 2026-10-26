"""Hábito «mover kWh del periodo A al B» (spec #18, ticket #20), datos SINTÉTICOS y cálculo a mano.
Lunes laborable 2026-06-08, 1 kWh por hora: 8 kWh en cada uno de P1, P2 y P3 (2.0TD). Precios 0,20 / 0,15 / 0,10.
Potencia 0,33 + 0,03. Línea base: energía 3,60 ; base 3,96 ; IE 0,2025 -> 0,20 ; sin IVA 4,16 ; total 5,03.
Mover 4 kWh de P1 a P3: energía 3,20 ; base 3,56 ; IE 0,18 ; sin IVA 3,74 ; total 4,53 ; ahorro 0,50.
Al 50 % (2 kWh): energía 3,40 ; base 3,76 ; IE 0,19 ; sin IVA 3,95 ; total 4,78 ; ahorro 0,25.
Al 25 % (1 kWh): energía 3,50 ; base 3,86 ; IE 0,20 ; sin IVA 4,06 ; total 4,91 ; ahorro 0,12.
Anual orientativo = ahorro x 365 / 1 día."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest

from estalvia.analysis.habito import Habito, HabitoImposible, evaluar_habito
from estalvia.analysis.nucleo import PrecioContrato
from estalvia.engine.calc import Periodo, SiteParams
from estalvia.engine.periods import Calendario
from estalvia.engine.rules import RuleSet
from estalvia.ingestion.hourly import ingest_hourly

RAIZ = Path(__file__).parents[1]
REGLAS = RuleSet([r for f in sorted((RAIZ / "rules").glob("*.yaml")) for r in RuleSet.from_yaml(f).rules])
CALENDARIO = Calendario.desde_directorio(RAIZ / "rules/calendar")
LUNES = Periodo(date(2026, 6, 8), date(2026, 6, 8))
SITIO = SiteParams("2.0TD", {"P1": D(4), "P2": D(4)})
PRECIOS = PrecioContrato(energia_eur_kwh={"P1": D("0.20"), "P2": D("0.15"), "P3": D("0.10")},
                         potencia_eur_kw_anio={"P1": D(30), "P2": D(3)})


def csv(inicio_utc: datetime, horas: int, estimada_en: int | None = None):
    filas = "".join(
        f"{(inicio_utc + timedelta(hours=h)).isoformat()},1,0,{'estimada' if h == estimada_en else 'real'}\n"
        for h in range(horas))
    return ingest_hourly(("instante,kwh,kvarh,tipo\n" + filas).encode(), "interno")


UN_DIA = csv(datetime(2026, 6, 7, 22, 0, tzinfo=timezone.utc), 24)


def evaluar(kwh="4", origen="P1", destino="P3", ingesta=UN_DIA, periodo=LUNES):
    return evaluar_habito(SITIO, ingesta, CALENDARIO, REGLAS, PRECIOS, periodo, Habito(origen, destino, D(kwh)))


def test_el_ahorro_se_calcula_al_25_50_y_100_por_ciento_con_el_motor():
    e = evaluar()
    assert e.base.total == D("5.03")
    assert e.ahorro == {25: D("0.12"), 50: D("0.25"), 100: D("0.50")}


def test_no_se_puede_mover_mas_de_lo_consumido_en_el_origen():
    with pytest.raises(HabitoImposible, match="origen"):
        evaluar(kwh="8.01")
    assert evaluar(kwh="8").ahorro[100] > 0


def test_un_habito_incoherente_se_rechaza():
    for malo in [dict(origen="P1", destino="P1"), dict(kwh="0"), dict(kwh="-1"), dict(destino="P4")]:
        with pytest.raises(HabitoImposible):
            evaluar(**malo)


def test_con_un_mes_o_menos_la_confianza_es_baja_y_el_anual_es_orientativo():
    e = evaluar()
    assert e.confianza == "baja" and e.meses_completos == 0
    assert e.ahorro_anual_orientativo == {25: D("43.80"), 50: D("91.25"), 100: D("182.50")}


def test_con_12_meses_reales_la_confianza_es_alta_y_con_una_estimada_es_media():
    inicio = datetime(2025, 6, 30, 22, 0, tzinfo=timezone.utc)  # 1 jul 2025 00:00 en Madrid
    horas = int((datetime(2026, 6, 30, 22, 0, tzinfo=timezone.utc) - inicio).total_seconds() // 3600)
    anual = csv(inicio, horas)
    assert evaluar(ingesta=anual).meses_completos == 12 and evaluar(ingesta=anual).confianza == "alta"
    assert evaluar(ingesta=csv(inicio, horas, estimada_en=100)).confianza == "media"
