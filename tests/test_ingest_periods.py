"""Seam: ingest_hourly(...) -> Ingesta; periodos tarifarios y totales por periodo. Datos sintéticos."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from estalvia.engine.errors import MissingDataError
from estalvia.engine.periods import Calendario
from estalvia.ingestion.hourly import ingest_hourly

MAD = ZoneInfo("Europe/Madrid")
CAL = Calendario.desde_directorio(Path(__file__).parents[1] / "rules" / "calendar")


def csv_dias(y, m, d, dias=1, kwh="1", kvarh="0.5") -> bytes:
    """Horas consecutivas desde las 00:00 locales del día dado, hasta las 00:00 locales de d+dias."""
    ini = datetime(y, m, d, tzinfo=MAD).astimezone(timezone.utc)
    fin_local = datetime(y, m, d, tzinfo=MAD) + timedelta(days=dias)
    fin = datetime(fin_local.year, fin_local.month, fin_local.day, tzinfo=MAD).astimezone(timezone.utc)
    filas = ["instante,kwh,kvarh,tipo"]
    t = ini
    while t < fin:
        filas.append(f"{t.astimezone(MAD).isoformat()},{kwh},{kvarh},real")
        t += timedelta(hours=1)
    return "\n".join(filas).encode()


def test_cada_hora_recibe_su_periodo_laborable_de_enero():
    # Miércoles 14-ene-2026, temporada alta (tipo A): P1 9-14 y 18-22, P2 8-9, 14-18 y 22-24, P6 0-8
    horas = {x.instante_local.hour: p for x, p in ingest_hourly(csv_dias(2026, 1, 14)).etiquetadas(CAL, tarifa="3.0TD")}
    assert horas[3] == "P6" and horas[8] == "P2" and horas[9] == "P1" and horas[13] == "P1"
    assert horas[14] == "P2" and horas[18] == "P1" and horas[22] == "P2" and horas[23] == "P2"


def test_totales_por_periodo_de_un_dia_a_mano():
    # 24 h con 1 kWh y 0,5 kVArh: P1 = 9 h, P2 = 7 h, P6 = 8 h
    t = ingest_hourly(csv_dias(2026, 1, 14)).totales_por_periodo(CAL, tarifa="3.0TD")
    assert {p: (v.kwh, v.kvarh) for p, v in t.items()} == {
        "P1": (D("9"), D("4.5")), "P2": (D("7"), D("3.5")), "P6": (D("8"), D("4.0"))}


def test_fin_de_semana_y_festivo_nacional_son_p6_todo_el_dia():
    sabado = ingest_hourly(csv_dias(2026, 5, 16)).totales_por_periodo(CAL, tarifa="3.0TD")
    inmaculada = ingest_hourly(csv_dias(2026, 12, 8)).totales_por_periodo(CAL, tarifa="3.0TD")
    assert set(sabado) == {"P6"} and inmaculada["P6"].kwh == D("24")


def test_festivo_solo_catalan_no_cambia_el_periodo():
    # 11-sep-2026 (viernes, Diada): temporada media (B1), el festivo es solo de Cataluña
    horas = {x.instante_local.hour: p for x, p in ingest_hourly(csv_dias(2026, 9, 11)).etiquetadas(CAL, tarifa="3.0TD")}
    assert horas[10] == "P3" and horas[3] == "P6" and horas[8] == "P4"


def test_dias_de_cambio_de_hora_son_domingo_p6_con_23_y_25_horas():
    assert ingest_hourly(csv_dias(2026, 3, 29)).totales_por_periodo(CAL, tarifa="3.0TD")["P6"].kwh == D("23")
    assert ingest_hourly(csv_dias(2026, 10, 25)).totales_por_periodo(CAL, tarifa="3.0TD")["P6"].kwh == D("25")


def test_los_totales_por_periodo_suman_el_consumo_total():
    ing = ingest_hourly(csv_dias(2026, 5, 11, dias=7, kwh="2.5"))
    t = ing.totales_por_periodo(CAL, tarifa="3.0TD")
    assert sum(v.kwh for v in t.values()) == sum(x.kwh for x in ing.lecturas) == D("420.0")


def test_rango_semiabierto_desde_hasta():
    ing = ingest_hourly(csv_dias(2026, 1, 14))
    ini = datetime(2026, 1, 14, 9, tzinfo=MAD)
    t = ing.totales_por_periodo(CAL, tarifa="3.0TD", desde=ini, hasta=datetime(2026, 1, 14, 14, tzinfo=MAD))
    assert {p: v.kwh for p, v in t.items()} == {"P1": D("5")}


def test_ano_sin_calendario_de_festivos_da_error_claro():
    with pytest.raises(MissingDataError, match="2027"):
        ingest_hourly(csv_dias(2027, 1, 13)).totales_por_periodo(CAL, tarifa="3.0TD")


def test_rango_sin_zona_horaria_se_rechaza():
    with pytest.raises(ValueError, match="zona horaria"):
        ingest_hourly(csv_dias(2026, 1, 14)).totales_por_periodo(CAL, tarifa="3.0TD", desde=datetime(2026, 1, 14))


def test_lecturas_fuera_del_rango_no_exigen_calendario_de_su_ano():
    # el fichero llega hasta 2027 (sin festivos cargados) pero la factura es de diciembre de 2026
    ing = ingest_hourly(csv_dias(2026, 12, 30, dias=3))
    t = ing.totales_por_periodo(CAL, tarifa="3.0TD", desde=datetime(2026, 12, 30, tzinfo=MAD),
                                hasta=datetime(2026, 12, 31, tzinfo=MAD))
    assert sum(v.kwh for v in t.values()) == D("24")


@pytest.mark.parametrize("dia,esperado", [
    # tipo B (marzo): P2 9-14 y 18-22, P3 8-9, 14-18 y 22-24, P6 0-8
    ((2026, 3, 11), {3: "P6", 8: "P3", 10: "P2", 15: "P3", 19: "P2", 23: "P3"}),
    # tipo B1 (junio): P3 9-14 y 18-22, P4 8-9, 14-18 y 22-24
    ((2026, 6, 10), {3: "P6", 8: "P4", 10: "P3", 15: "P4", 19: "P3", 23: "P4"}),
    # tipo C (mayo): P4 9-14 y 18-22, P5 8-9, 14-18 y 22-24
    ((2026, 5, 13), {3: "P6", 8: "P5", 10: "P4", 15: "P5", 19: "P4", 23: "P5"}),
])
def test_horas_de_los_tipos_b_b1_y_c(dia, esperado):
    horas = {x.instante_local.hour: p for x, p in ingest_hourly(csv_dias(*dia)).etiquetadas(CAL, tarifa="3.0TD")}
    assert {h: horas[h] for h in esperado} == esperado


def test_reyes_es_tipo_d_aunque_sea_laborable():
    assert set(ingest_hourly(csv_dias(2026, 1, 6)).totales_por_periodo(CAL, tarifa="3.0TD")) == {"P6"}  # martes


@pytest.mark.parametrize("desde,hasta", [
    (datetime(2026, 1, 14, 10, tzinfo=MAD), datetime(2026, 1, 14, 10, tzinfo=MAD)),
    (datetime(2026, 1, 14, 12, tzinfo=MAD), datetime(2026, 1, 14, 10, tzinfo=MAD)),
])
def test_rango_vacio_o_invertido_se_rechaza(desde, hasta):
    with pytest.raises(ValueError, match="desde"):
        ingest_hourly(csv_dias(2026, 1, 14)).totales_por_periodo(CAL, tarifa="3.0TD", desde=desde, hasta=hasta)
