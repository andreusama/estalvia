"""Seam: ingest_hourly(csv_bytes) -> lecturas. Datos sintéticos."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from zoneinfo import ZoneInfo

import pytest

from estalvia.ingestion.hourly import IngestError, ingest_hourly

MAD = ZoneInfo("Europe/Madrid")


def csv_horas(inicio_utc: datetime, n: int, kwh="1.5", kvarh="0.2", tipo="real") -> bytes:
    """CSV sintético con n horas consecutivas desde un instante UTC, con offset de Madrid."""
    filas = ["instante,kwh,kvarh,tipo"]
    for i in range(n):
        t = (inicio_utc + timedelta(hours=i)).astimezone(MAD)
        filas.append(f"{t.isoformat()},{kwh},{kvarh},{tipo}")
    return "\n".join(filas).encode()


def dia_local(y, m, d) -> tuple[datetime, int]:
    """Inicio UTC y número real de horas de un día local de Madrid (calculado con el reloj de zoneinfo)."""
    ini = datetime(y, m, d, tzinfo=MAD).astimezone(timezone.utc)
    fin = datetime(y, m, d, tzinfo=MAD) + timedelta(days=1)
    fin = datetime(fin.year, fin.month, fin.day, tzinfo=MAD).astimezone(timezone.utc)
    return ini, int((fin - ini).total_seconds() // 3600)


def test_dia_normal_24_lecturas_con_instante_madrid_y_utc():
    ini, n = dia_local(2026, 6, 10)
    lecturas = ingest_hourly(csv_horas(ini, n))
    assert len(lecturas) == 24
    primera = lecturas[0]
    assert primera.instante_utc == datetime(2026, 6, 9, 22, 0, tzinfo=timezone.utc)
    assert primera.instante_local.utcoffset() == timedelta(hours=2)
    assert primera.instante_local.tzinfo == MAD
    assert (primera.kwh, primera.kvarh, primera.tipo) == (D("1.5"), D("0.2"), "real")


def test_dia_de_25_horas_octubre_tiene_25_lecturas():
    ini, n = dia_local(2026, 10, 25)
    assert n == 25  # valor conocido: último domingo de octubre
    lecturas = ingest_hourly(csv_horas(ini, n))
    assert len(lecturas) == 25
    # La hora 02:00 local aparece dos veces, una con +02:00 y otra con +01:00
    dos = [x for x in lecturas if x.instante_local.hour == 2]
    assert [x.instante_local.utcoffset() for x in dos] == [timedelta(hours=2), timedelta(hours=1)]
    assert dos[0].instante_utc != dos[1].instante_utc


def test_dia_de_23_horas_marzo_tiene_23_lecturas():
    ini, n = dia_local(2026, 3, 29)
    assert n == 23  # valor conocido: último domingo de marzo
    lecturas = ingest_hourly(csv_horas(ini, n))
    assert len(lecturas) == 23
    assert 2 not in {x.instante_local.hour for x in lecturas}  # la 02:00 local no existe


def test_ida_y_vuelta_madrid_utc_sin_perdida():
    ini, n = dia_local(2026, 10, 25)
    for x in ingest_hourly(csv_horas(ini, n)):
        assert x.instante_utc.astimezone(MAD) == x.instante_local
        assert x.instante_local.astimezone(timezone.utc) == x.instante_utc


def test_cantidades_son_decimal_exactos():
    ini, n = dia_local(2026, 6, 10)
    x = ingest_hourly(csv_horas(ini, 1, kwh="0.1", kvarh="0.30"))[0]
    assert isinstance(x.kwh, D) and isinstance(x.kvarh, D)
    assert x.kwh + D("0.2") == D("0.3")  # con float daría 0.30000000000000004


@pytest.mark.parametrize("fila,fragmento", [
    ("2026-06-10T00:00:00,1,1,real", "sin desfase"),       # sin zona: no se supone
    ("2026-06-10T00:00:00+02:00,abc,1,real", "kwh"),
    ("2026-06-10T00:00:00+02:00,-1,1,real", "kwh"),
    ("2026-06-10T00:00:00+02:00,1,1,dudosa", "tipo"),
    ("ayer,1,1,real", "ISO 8601"),
])
def test_entradas_ambiguas_o_invalidas_se_rechazan_con_la_linea(fila, fragmento):
    with pytest.raises(IngestError, match=fragmento) as e:
        ingest_hourly(f"instante,kwh,kvarh,tipo\n{fila}\n".encode())
    assert "línea 2" in str(e.value)


def test_cabecera_incorrecta_se_rechaza():
    with pytest.raises(IngestError, match="cabecera"):
        ingest_hourly(b"fecha,hora,kwh\n")


def test_instante_duplicado_se_rechaza():
    ini, _ = dia_local(2026, 6, 10)
    fila = csv_horas(ini, 1).decode().splitlines()[1]
    with pytest.raises(IngestError, match="duplicad"):
        ingest_hourly(("instante,kwh,kvarh,tipo\n" + fila + "\n" + fila + "\n").encode())
