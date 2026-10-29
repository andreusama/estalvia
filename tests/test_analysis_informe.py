"""Informe automático (spec #18, ticket #33), datos SINTÉTICOS y cálculo a mano.
Lunes laborable 2026-06-08, 1 kWh por hora: 8 kWh en cada uno de P1, P2 y P3 (2.0TD). Precios 0,20 / 0,15 / 0,10.
Potencia 4 kW: 0,33 + 0,03. Energía 1,60 + 1,20 + 0,80 = 3,60. IE 0,20 ; IVA 0,87 ; total 5,03.
Reparto: potencia 0,36 ; energía 3,60 ; impuestos 0,20 + 0,87 = 1,07 ; suma 5,03.
Mover todo P1 (8 kWh) a P3: energía 2,80 ; base 3,16 ; IE 0,16 ; sin IVA 3,32 ; total 4,02 ; ahorro 1,01.
Mover todo P2 (8 kWh) a P3: energía 3,20 ; base 3,56 ; IE 0,18 ; sin IVA 3,74 ; total 4,53 ; ahorro 0,50.
Al 25 y 50 %: P1->P3 0,25 y 0,50 ; P2->P3 0,12 y 0,25. Anual orientativo = ahorro x 365 / 1 día."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

from estalvia.analysis.informe import construir_informe
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


def consumo(inicio_utc: datetime, horas: int, kwh=lambda h: 1):
    filas = "".join(f"{(inicio_utc + timedelta(hours=h)).isoformat()},{kwh(h)},0,real\n" for h in range(horas))
    return ingest_hourly(("instante,kwh,kvarh,tipo\n" + filas).encode(), "interno")


UN_DIA = consumo(datetime(2026, 6, 7, 22, 0, tzinfo=timezone.utc), 24)


def informe(ingesta=UN_DIA, periodo=LUNES):
    return construir_informe(SITIO, ingesta, CALENDARIO, REGLAS, PRECIOS, periodo)


def test_el_reparto_del_gasto_suma_el_total_de_la_linea_base():
    i = informe()
    assert i.total == D("5.03")
    assert {p.nombre: p.importe for p in i.reparto} == {
        "Potencia contratada": D("0.36"), "Energía consumida": D("3.60"), "Impuestos": D("1.07")}
    assert sum(p.importe for p in i.reparto) == i.total
    assert all(p.explicacion for p in i.reparto)


def test_las_franjas_dicen_cuanto_consumes_y_cuanto_pagas_en_cada_una():
    f = {x.periodo: x for x in informe().franjas}
    assert [(x.nivel, x.kwh, x.coste_energia) for x in informe().franjas] == [
        ("cara", D(8), D("1.60")), ("normal", D(8), D("1.20")), ("barata", D(8), D("0.80"))]
    assert f["P1"].nombre == "Horas caras" and f["P3"].nombre == "Horas baratas"
    assert f["P1"].horario == "10-14 h y 18-22 h" and f["P3"].horario == "0-8 h"
    assert f["P1"].porcentaje_consumo == D("33.3")


# Viernes 2026-06-12 a 1 kWh/h y sábado 2026-06-13 a 2 kWh/h (el sábado todo es P3, 0,10).
# Viernes: 3,60 de energía (P1 1,60 ; P2 1,20 ; P3 0,80). Sábado: 48 x 0,10 = 4,80. Total energía 8,40 ; 72 kWh.
# Fondo = percentil 10 (rango más cercano) de las 48 horas = 1 kWh/h: viernes 3,60 + sábado 24 x 0,10 = 6,00 ; 48 kWh.
# Horas más caras (suma de las dos jornadas): 10-13 y 18-21 h cuestan 0,20 + 0,20 = 0,40 ; el resto, menos.
FIN_DE_SEMANA = Periodo(date(2026, 6, 12), date(2026, 6, 13))
DOS_DIAS = consumo(datetime(2026, 6, 11, 22, 0, tzinfo=timezone.utc), 48, kwh=lambda h: 1 if h < 24 else 2)


def informe_viernes_sabado():
    return informe(DOS_DIAS, FIN_DE_SEMANA)


def test_el_mapa_de_calor_da_el_kwh_medio_por_dia_de_la_semana_y_hora():
    mapa = informe_viernes_sabado().mapa
    assert [f.dia for f in mapa] == ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    viernes, sabado = mapa[4], mapa[5]
    assert [c.kwh for c in viernes.celdas] == [D(1)] * 24 and [c.kwh for c in sabado.celdas] == [D(2)] * 24
    assert all(c.kwh is None and c.intensidad == 0 for c in mapa[0].celdas)
    assert {c.intensidad for c in viernes.celdas} == {4} and {c.intensidad for c in sabado.celdas} == {9}


def test_laborables_y_fines_de_semana_se_comparan_por_dia_medio():
    i = informe_viernes_sabado()
    assert (i.laborables.dias, i.laborables.kwh_por_dia, i.laborables.coste_energia) == (1, D(24), D("3.60"))
    assert (i.finde.dias, i.finde.kwh_por_dia, i.finde.coste_energia) == (1, D(48), D("4.80"))


def test_el_consumo_de_fondo_es_lo_que_gastas_incluso_en_tus_horas_mas_tranquilas():
    f = informe_viernes_sabado().fondo
    assert (f.kwh_hora, f.kwh, f.coste_energia, f.porcentaje_consumo) == (D(1), D(48), D("6.00"), D("66.7"))


def test_los_dias_y_las_horas_mas_caras_se_ordenan_por_coste_de_energia():
    i = informe_viernes_sabado()
    assert [(d.dia, d.kwh, d.coste_energia) for d in i.dias_caros] == [
        (date(2026, 6, 13), D(48), D("4.80")), (date(2026, 6, 12), D(24), D("3.60"))]
    assert [(h.hora, h.coste_energia) for h in i.horas_caras] == [(10, D("0.40")), (11, D("0.40")), (12, D("0.40"))]


def test_los_hallazgos_mueven_consumo_a_horas_baratas_y_se_ordenan_por_techo_de_ahorro():
    h = informe().hallazgos
    assert [(x.origen, x.destino, x.kwh_origen) for x in h] == [("P1", "P3", D(8)), ("P2", "P3", D(8))]
    assert h[0].ahorro == {25: D("0.25"), 50: D("0.50"), 100: D("1.01")}
    assert h[1].ahorro == {25: D("0.12"), 50: D("0.25"), 100: D("0.50")}
    assert h[0].ahorro_anual == {25: D("91.25"), 50: D("182.50"), 100: D("368.65")}
    assert (h[0].origen_franja.nombre, h[0].destino_franja.nombre) == ("Horas caras", "Horas baratas")
    assert h[1].origen_franja.nombre == "Horas normales"


def test_el_techo_nunca_mueve_mas_de_lo_consumido_y_se_dice_que_es_teorico():
    for x in informe().hallazgos:
        assert x.kwh_movidos[100] == x.kwh_origen and x.kwh_movidos[25] == x.kwh_origen / 4
        assert x.confianza == "baja"  # un solo día


def test_sin_ahorro_posible_no_hay_hallazgos():
    todo_barato = consumo(datetime(2026, 6, 13, 22, 0, tzinfo=timezone.utc), 24)  # domingo: todo P3
    domingo = Periodo(date(2026, 6, 14), date(2026, 6, 14))
    assert informe(todo_barato, domingo).hallazgos == ()
