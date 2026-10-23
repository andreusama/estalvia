"""Seam: ingest_hourly(datos, lector="fecha_hora_kwh"). Datos SINTÉTICOS (el fichero real no está en el repo)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from estalvia.engine.periods import Calendario
from estalvia.ingestion.hourly import IngestError, ingest_hourly

MAD = ZoneInfo("Europe/Madrid")
CAL = Calendario.desde_directorio(Path(__file__).parents[1] / "rules" / "calendar")
L = "fecha_hora_kwh"


def csv_portal(filas, cabecera="date;hour;kwh") -> bytes:
    return (cabecera + "\r\n" + "".join(f"{f}\r\n" for f in filas)).encode()


def dia(fecha, horas=24, kwh="1,0"):
    return [f"{fecha};{h};{kwh}" for h in range(1, horas + 1)]


def test_la_hora_n_es_el_intervalo_que_termina_en_n():
    lecturas = ingest_hourly(csv_portal(dia("2026-09-01")), lector=L).lecturas
    assert len(lecturas) == 24
    assert lecturas[0].instante_utc == datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc)  # hora 1 = 00:00+02:00
    assert lecturas[0].instante_local == datetime(2026, 9, 1, 0, 0, tzinfo=MAD)
    assert lecturas[23].instante_local == datetime(2026, 9, 1, 23, 0, tzinfo=MAD)  # hora 24 = 23:00-24:00


def test_kwh_con_coma_decimal_exacto_y_sin_kvarh_ni_marca_de_tipo():
    x = ingest_hourly(csv_portal(["2026-09-01;1;0,123456789012345678"]), lector=L).lecturas[0]
    assert x.kwh == D("0.123456789012345678") and isinstance(x.kwh, D)
    assert x.kvarh is None  # el formato no lo trae: no se supone 0
    assert x.tipo == "desconocida"  # no se supone "real"


def test_la_calidad_cuenta_las_lecturas_de_tipo_desconocido():
    r = ingest_hourly(csv_portal(dia("2026-09-01")), lector=L)
    m = r.calidad.meses[(2026, 9)]
    assert (m.reales, m.estimadas, m.desconocidas) == (0, 0, 24)


def test_dia_de_25_horas_acepta_las_horas_1_a_25():
    lecturas = ingest_hourly(csv_portal(dia("2026-10-25", horas=25)), lector=L).lecturas
    assert len(lecturas) == 25
    assert lecturas[-1].instante_local == datetime(2026, 10, 25, 23, 0, tzinfo=MAD)
    assert lecturas[-1].instante_utc == lecturas[0].instante_utc + timedelta(hours=24)


def test_dia_de_23_horas_acepta_1_a_23_y_rechaza_la_hora_24():
    assert len(ingest_hourly(csv_portal(dia("2026-03-29", horas=23)), lector=L).lecturas) == 23
    with pytest.raises(IngestError, match="línea 25") as e:
        ingest_hourly(csv_portal(dia("2026-03-29", horas=24)), lector=L)
    assert "hora" in str(e.value)


def test_hora_fuera_del_dia_en_un_dia_normal_se_rechaza():
    with pytest.raises(IngestError, match="línea 2"):
        ingest_hourly(csv_portal(["2026-09-01;25;1,0"]), lector=L)


@pytest.mark.parametrize("fila,fragmento", [
    ("2026-09-01;1;0.5", "coma"),            # separador decimal con punto
    ("2026-09-01;1;abc", "kwh"),
    ("2026-09-01;1;NaN", "kwh"),
    ("01/09/2026;1;1,0", "date"),
    ("2026-09-01;0;1,0", "hora"),
    ("2026-09-01;uno;1,0", "hora"),
])
def test_entradas_invalidas_se_rechazan_con_la_linea(fila, fragmento):
    with pytest.raises(IngestError, match=fragmento) as e:
        ingest_hourly(csv_portal([fila]), lector=L)
    assert "línea 2" in str(e.value)


def test_cabecera_incorrecta_duplicados_y_lector_desconocido():
    with pytest.raises(IngestError, match="cabecera"):
        ingest_hourly(csv_portal(["2026-09-01;1;1,0"], cabecera="fecha;hora;consumo"), lector=L)
    with pytest.raises(IngestError, match="duplicad"):
        ingest_hourly(csv_portal(["2026-09-01;1;1,0", "2026-09-01;1;2,0"]), lector=L)
    with pytest.raises(IngestError, match="lector"):
        ingest_hourly(csv_portal(dia("2026-09-01")), lector="no_existe")


def test_totales_por_periodo_dejan_kvarh_desconocido_en_none():
    t = ingest_hourly(csv_portal(dia("2026-09-10")), lector=L).totales_por_periodo(CAL, tarifa="3.0TD")
    assert sum(v.kwh for v in t.values()) == D("24.0")
    assert all(v.kvarh is None for v in t.values())


def test_etiquetado_2_0td_con_tres_periodos_de_energia():
    # jueves 10-sep-2026, 1 kWh por hora: P1 = 10-14 y 18-22 (8 h), P2 = 8-10, 14-18 y 22-24 (8 h), P3 = 0-8 (8 h)
    ing = ingest_hourly(csv_portal(dia("2026-09-10")), lector=L)
    t = ing.totales_por_periodo(CAL, tarifa="2.0TD")
    assert {p: v.kwh for p, v in t.items()} == {"P1": D("8.0"), "P2": D("8.0"), "P3": D("8.0")}
    # 3.0TD (por defecto), septiembre = temporada media, tipo B1:
    # P3 = 10-14 y 18-22 (9 h), P4 = 8-10, 14-18 y 22-24 (7 h), P6 = 0-8 (8 h)
    assert {p: v.kwh for p, v in ing.totales_por_periodo(CAL, tarifa="3.0TD").items()} == {
        "P3": D("9.0"), "P4": D("7.0"), "P6": D("8.0")}
    with pytest.raises(ValueError, match="tarifa"):
        ing.totales_por_periodo(CAL, tarifa="9.9TD")


def test_hora_final_ausente_de_un_dia_de_25_horas_se_informa_como_hueco():
    filas = dia("2026-10-25", horas=24)  # falta la hora 25, la última del día
    r = ingest_hourly(csv_portal(filas), lector=L)
    ultimo_dia_utc = datetime(2026, 10, 24, 22, 0, tzinfo=timezone.utc) + timedelta(hours=24)  # hora 25 = 23:00 local
    assert r.calidad.huecos == [ultimo_dia_utc]


def test_horas_ausentes_al_principio_del_primer_dia_se_informan_como_huecos():
    filas = [f"2026-09-01;{h};1,0" for h in range(5, 25)]  # faltan las horas 1 a 4
    r = ingest_hourly(csv_portal(filas), lector=L)
    inicio = datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc)
    assert r.calidad.huecos == [inicio + timedelta(hours=i) for i in range(4)]


def test_un_mes_solo_de_lecturas_desconocidas_esta_completo_en_cobertura():
    # Decisión: `completo` mide cobertura de horas, no la calidad real/estimada (eso es `desconocidas`).
    filas = [f for d in range(1, 31) for f in dia(f"2026-06-{d:02d}")]
    m = ingest_hourly(csv_portal(filas), lector=L).calidad.meses[(2026, 6)]
    assert (m.completo, m.desconocidas, m.reales, m.estimadas) == (True, 720, 0, 0)
