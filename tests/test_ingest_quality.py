"""Seam: ingest_hourly(csv_bytes) -> lecturas + informe de calidad. Datos sintéticos."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from estalvia.ingestion.hourly import ingest_hourly

MAD = ZoneInfo("Europe/Madrid")


def mes_utc(y, m):
    ini = datetime(y, m, 1, tzinfo=MAD).astimezone(timezone.utc)
    sig = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=MAD).astimezone(timezone.utc)
    return ini, int((sig - ini).total_seconds() // 3600)


def csv_de(horas_utc, tipo=lambda i: "real") -> bytes:
    filas = ["instante,kwh,kvarh,tipo"]
    for i, t in enumerate(horas_utc):
        filas.append(f"{t.astimezone(MAD).isoformat()},1,0,{tipo(i)}")
    return "\n".join(filas).encode()


def horas(ini, n):
    return [ini + timedelta(hours=i) for i in range(n)]


def test_hora_que_falta_se_informa_y_no_aparece_en_las_lecturas():
    ini, n = mes_utc(2026, 6)
    todas = horas(ini, n)
    quitada = todas.pop(100)
    r = ingest_hourly(csv_de(todas))
    assert quitada not in [x.instante_utc for x in r.lecturas]
    assert len(r.lecturas) == 719
    assert r.calidad.huecos == [quitada]


def test_reales_y_estimadas_se_cuentan_por_separado_por_mes():
    ini, n = mes_utc(2026, 6)
    r = ingest_hourly(csv_de(horas(ini, n), tipo=lambda i: "estimada" if i < 10 else "real"))
    m = r.calidad.meses[(2026, 6)]
    assert (m.reales, m.estimadas) == (710, 10)


def test_mes_completo_y_mes_incompleto_son_identificables():
    ini, n = mes_utc(2026, 6)
    assert n == 720
    ok = ingest_hourly(csv_de(horas(ini, n)))
    assert ok.calidad.meses[(2026, 6)].completo is True
    assert ok.calidad.meses[(2026, 6)].faltantes == 0
    incompleto = horas(ini, n)[:-24]  # falta el último día
    r = ingest_hourly(csv_de(incompleto))
    m = r.calidad.meses[(2026, 6)]
    assert (m.completo, m.faltantes) == (False, 24)


def test_meses_con_cambio_de_hora_se_completan_con_743_y_745_horas():
    for (y, mes, esperado) in [(2026, 3, 743), (2026, 10, 745)]:
        ini, n = mes_utc(y, mes)
        assert n == esperado
        r = ingest_hourly(csv_de(horas(ini, n)))
        assert r.calidad.meses[(y, mes)].completo is True


def test_un_mes_sin_lecturas_entre_dos_con_datos_aparece_como_incompleto():
    j, nj = mes_utc(2026, 6)
    s, ns = mes_utc(2026, 8)
    r = ingest_hourly(csv_de(horas(j, nj) + horas(s, ns)))
    julio = r.calidad.meses[(2026, 7)]
    assert (julio.reales, julio.estimadas, julio.completo) == (0, 0, False)
    assert julio.faltantes == 744
    assert len(r.calidad.huecos) == 744  # cada hora de julio se informa y no se rellena
