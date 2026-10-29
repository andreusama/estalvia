"""Ofertas de otra comercializadora (spec #18, ticket #21), datos SINTÉTICOS y cálculo a mano.
Lunes laborable 2026-06-08, 1 kWh por hora: 8 kWh en cada uno de P1, P2 y P3 (2.0TD), potencia 4 kW. Línea base del
contrato (0,20 / 0,15 / 0,10 ; potencia 30 y 3): total 5,03.

Oferta FIJA 0,18 / 0,12 / 0,09 ; potencia 28 y 2,5 EUR/kW/año:
  energía 1,44 + 0,96 + 0,72 = 3,12 ; potencia 0,31 + 0,03 = 0,34 ; base 3,46 ; IE 0,18 ; sin IVA 3,64 ; total 4,40 ;
  ahorro 5,03 - 4,40 = 0,63.

Oferta INDEXADA (margen 0,010 EUR/kWh, potencia 30 y 3). Precio de mercado de prueba (EUR/MWh, igual en los 4 cuartos
de hora de la hora salvo la 11 y la 12 y ambas promedian lo mismo): 100 en 10-13 h, 200 en 18-21 h (P1: media 150) ;
80 en P2 ; 40 en P3. Peajes + cargos + pago por capacidad de las reglas de 2026 (BOE):
P1 0,033261 + 0,064292 + 0,000800 ; P2 0,016409 + 0,012858 + 0,000133 ;
P3 0,000077 + 0,003215 (P3 no tiene pago por capacidad: casilla en blanco en el BOE).
  Precio efectivo: P1 0,150 + 0,010 + 0,098353 = 0,258353 ; P2 0,080 + 0,010 + 0,029400 = 0,119400 ;
  P3 0,040 + 0,010 + 0,003292 = 0,053292.
  Energía 2,07 + 0,96 + 0,43 = 3,46 ; potencia 0,36 ; base 3,82 ; IE 0,20 ; sin IVA 4,02 ; total 4,86 ; ahorro 0,17."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

from estalvia.analysis.nucleo import PrecioContrato
from estalvia.analysis.ofertas import OfertaFija, OfertaIndexada, evaluar_oferta
from estalvia.engine.calc import Periodo, SiteParams
from estalvia.engine.periods import Calendario
from estalvia.engine.rules import RuleSet
from estalvia.ingestion.hourly import ingest_hourly
from estalvia.prices.store import PricePoint, PriceResult

RAIZ = Path(__file__).parents[1]
REGLAS = RuleSet([r for f in sorted((RAIZ / "rules").glob("*.yaml")) for r in RuleSet.from_yaml(f).rules])
CALENDARIO = Calendario.desde_directorio(RAIZ / "rules/calendar")
LUNES = Periodo(date(2026, 6, 8), date(2026, 6, 8))
SITIO = SiteParams("2.0TD", {"P1": D(4), "P2": D(4)})
CONTRATO = PrecioContrato(energia_eur_kwh={"P1": D("0.20"), "P2": D("0.15"), "P3": D("0.10")},
                          potencia_eur_kw_anio={"P1": D(30), "P2": D(3)})
INICIO = datetime(2026, 6, 7, 22, 0, tzinfo=timezone.utc)  # 00:00 hora de Madrid del lunes
CONSUMO = ingest_hourly(("instante,kwh,kvarh,tipo\n" + "".join(
    f"{(INICIO + timedelta(hours=h)).isoformat()},1,0,real\n" for h in range(24))).encode(), "interno")


def evaluar(oferta, mercado=None):
    return evaluar_oferta(SITIO, CONSUMO, CALENDARIO, REGLAS, CONTRATO, LUNES, oferta, mercado)


def test_una_oferta_fija_se_calcula_con_el_motor_y_se_compara_con_la_linea_base():
    oferta = OfertaFija("Fija de prueba", {"P1": D("0.18"), "P2": D("0.12"), "P3": D("0.09")},
                        {"P1": D(28), "P2": D("2.5")}, date(2026, 10, 1), "captura manual de prueba")
    r = evaluar(oferta)
    assert (r.total, r.ahorro, r.completo) == (D("4.40"), D("0.63"), True)
    assert (r.tipo, r.capturada, r.avisos) == ("fija", date(2026, 10, 1), ())


def _cuartos(hora: int) -> list[int]:
    if hora == 11:
        return [90, 110, 90, 110]
    if hora == 12:
        return [80, 120, 100, 100]
    precio = 100 if 10 <= hora <= 13 else 200 if 18 <= hora <= 21 else 40 if hora < 8 else 80
    return [precio] * 4


def mercado(sin_horas=(), completo=True):
    puntos = [PricePoint(INICIO + timedelta(hours=h, minutes=15 * q), D(p))
              for h in range(24) if h not in sin_horas for q, p in enumerate(_cuartos(h))]
    capturado = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
    return PriceResult(puntos, completo, capturado if completo else None, "redata", None if completo else "sin red",
                       timedelta(minutes=15), "Fuente: Red Eléctrica (www.ree.es), REData")


INDEXADA = OfertaIndexada("Indexada de prueba", D("0.010"), {"P1": D(30), "P2": D(3)}, date(2026, 10, 1),
                          "captura manual de prueba", otros_eur_kwh=D(0))


def test_una_oferta_indexada_usa_el_precio_de_mercado_de_cada_hora_mas_peajes_cargos_y_capacidad():
    r = evaluar(INDEXADA, mercado())
    assert (r.total, r.ahorro, r.completo, r.tipo) == (D("4.86"), D("0.17"), True, "indexada")
    assert r.precios_capturados_en == datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
    assert r.atribucion == "Fuente: Red Eléctrica (www.ree.es), REData" and r.avisos == ()


def test_sin_precios_de_mercado_la_oferta_indexada_sale_marcada_y_sin_importe():
    for caso in (None, mercado(completo=False)):
        r = evaluar(INDEXADA, caso)
        assert (r.total, r.ahorro, r.completo) == (None, None, False)
        assert r.avisos and "sin precios de mercado" in r.avisos[0]


def test_si_faltan_precios_de_algunas_horas_no_se_rellenan_y_el_resultado_lo_dice():
    r = evaluar(INDEXADA, mercado(sin_horas=(3, 15)))
    assert (r.total, r.ahorro, r.completo) == (None, None, False)
    assert "2 horas" in r.avisos[0]


def test_una_hora_con_solo_parte_de_sus_cuartos_de_hora_cuenta_como_hora_sin_precio():
    parcial = mercado()
    quitado = parcial.puntos[:-1]  # falta el último cuarto de hora de la última hora
    r = evaluar(INDEXADA, PriceResult(quitado, True, parcial.capturado_en, "redata", None, parcial.paso, None))
    assert r.total is None and "1 horas" in r.avisos[0]


def test_sin_declarar_servicios_de_ajuste_se_calcula_pero_con_aviso_y_la_oferta_fija_no_avisa():
    sin_declarar = OfertaIndexada(**{**INDEXADA.__dict__, "otros_eur_kwh": None})
    r = evaluar(sin_declarar, mercado())
    assert r.total == D("4.86") and len(r.avisos) == 1 and "servicios de ajuste" in r.avisos[0]


def test_los_otros_costes_declarados_suben_el_total():
    con_ajustes = OfertaIndexada(**{**INDEXADA.__dict__, "otros_eur_kwh": D("0.020")})
    # +0,020 EUR/kWh x 24 kWh = 0,48 de energía ; base 4,30 ; IE 0,22 ; sin IVA 4,52 ; total 5,47
    assert evaluar(con_ajustes, mercado()).total == D("5.47")
