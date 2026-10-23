"""Seam: PriceStore.get(desde, hasta, as_of) con una PriceSource falsa. Datos sintéticos."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from estalvia.prices.store import PricePoint, PriceStore, SourceError

T0 = datetime(2026, 6, 10, 0, 0, tzinfo=timezone.utc)
DESDE, HASTA = T0, T0 + timedelta(hours=3)


class FuenteFalsa:
    name = "falsa"

    def __init__(self, valor="50", fallos=0):
        self.valor, self.fallos, self.llamadas = valor, fallos, 0

    def fetch(self, desde, hasta):
        self.llamadas += 1
        if self.fallos > 0:
            self.fallos -= 1
            raise SourceError("caída simulada")
        return [PricePoint(desde + timedelta(hours=i), D(self.valor) + i) for i in range(3)]


class Reloj:
    def __init__(self):
        self.t = datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def avanza(self, **kw):
        self.t += timedelta(**kw)


def tienda(fuente, reloj=None, **kw):
    pausas = []
    return PriceStore(fuente, clock=reloj or Reloj(), sleep=pausas.append, **kw), pausas


def test_primera_consulta_trae_precios_con_fecha_de_captura():
    reloj = Reloj()
    t, _ = tienda(FuenteFalsa(), reloj)
    r = t.get(DESDE, HASTA)
    assert r.completo and r.error is None
    assert [p.eur_mwh for p in r.puntos] == [D("50"), D("51"), D("52")]
    assert r.capturado_en == reloj.t and r.fuente == "falsa"


def test_segunda_consulta_igual_sale_de_la_cache():
    f = FuenteFalsa()
    t, _ = tienda(f)
    a, b = t.get(DESDE, HASTA), t.get(DESDE, HASTA)
    assert f.llamadas == 1 and a == b


def test_una_consulta_se_reproduce_con_su_fecha_de_captura():
    f, reloj = FuenteFalsa("50"), Reloj()
    t, _ = tienda(f, reloj)
    primera = t.get(DESDE, HASTA)
    reloj.avanza(days=1)
    f.valor = "70"  # la fuente cambia (p. ej. revisión de precios)
    segunda = t.get(DESDE, HASTA, refresh=True)
    assert segunda.puntos[0].eur_mwh == D("70")
    de_nuevo = t.get(DESDE, HASTA, as_of=primera.capturado_en)
    assert de_nuevo.puntos == primera.puntos and de_nuevo.capturado_en == primera.capturado_en
    assert t.get(DESDE, HASTA, as_of=segunda.capturado_en).puntos == segunda.puntos


def test_as_of_sin_captura_previa_es_incompleto_y_no_consulta_la_fuente():
    f, reloj = FuenteFalsa(), Reloj()
    t, _ = tienda(f, reloj)
    r = t.get(DESDE, HASTA, as_of=reloj.t - timedelta(days=30))
    assert not r.completo and r.puntos == [] and f.llamadas == 0


def test_fallo_de_la_fuente_da_resultado_incompleto_sin_valores_supuestos():
    f = FuenteFalsa(fallos=99)
    t, _ = tienda(f)
    r = t.get(DESDE, HASTA)
    assert not r.completo and r.puntos == [] and "caída simulada" in r.error
    f.fallos = 0
    assert t.get(DESDE, HASTA).completo  # el fallo no quedó cacheado


def test_reintentos_con_espera_exponencial():
    f = FuenteFalsa(fallos=2)
    t, pausas = tienda(f, reintentos=3, espera_base=1.0)
    assert t.get(DESDE, HASTA).completo and f.llamadas == 3
    assert pausas == [1.0, 2.0]
    g = FuenteFalsa(fallos=99)
    t2, pausas2 = tienda(g, reintentos=3, espera_base=1.0)
    assert not t2.get(DESDE, HASTA).completo and g.llamadas == 3 and pausas2 == [1.0, 2.0]


def test_fuente_que_responde_sin_precios_es_incompleto():
    class Vacia(FuenteFalsa):
        def fetch(self, desde, hasta):
            return []

    t, _ = tienda(Vacia())
    r = t.get(DESDE, HASTA)
    assert not r.completo and r.puntos == [] and "sin precios" in r.error


def test_fecha_sin_zona_horaria_se_rechaza():
    t, _ = tienda(FuenteFalsa())
    with pytest.raises(ValueError, match="zona horaria"):
        t.get(datetime(2026, 6, 10), datetime(2026, 6, 11))


class FuenteParcial(FuenteFalsa):
    """Responde con huecos: cuartohoraria con un cuarto de hora ausente."""

    def fetch(self, desde, hasta):
        self.llamadas += 1
        pts = [PricePoint(desde + timedelta(minutes=15 * i), D(i)) for i in range(12)]
        del pts[5]
        return pts


def test_respuesta_con_huecos_es_incompleta_y_no_se_cachea():
    f = FuenteParcial()
    t, _ = tienda(f)
    r = t.get(DESDE, HASTA)
    assert not r.completo and r.puntos == [] and "faltan 1" in r.error
    t.get(DESDE, HASTA)
    assert f.llamadas == 2


def test_respuesta_que_no_llega_al_final_del_rango_es_incompleta():
    class Corta(FuenteFalsa):
        def fetch(self, desde, hasta):
            return [PricePoint(desde + timedelta(hours=i), D(i)) for i in range(2)]  # falta la última hora

    t, _ = tienda(Corta())
    assert not t.get(DESDE, HASTA).completo


def test_resultado_expone_la_resolucion_y_la_atribucion():
    class Cuartohoraria(FuenteFalsa):
        atribucion = "Fuente: www.ree.es"

        def fetch(self, desde, hasta):
            return [PricePoint(desde + timedelta(minutes=15 * i), D(i)) for i in range(12)]

    r = tienda(Cuartohoraria())[0].get(DESDE, HASTA)
    assert r.completo and r.paso == timedelta(minutes=15) and r.atribucion == "Fuente: www.ree.es"


def test_error_permanente_no_se_reintenta():
    class Mala(FuenteFalsa):
        def fetch(self, desde, hasta):
            self.llamadas += 1
            raise SourceError("petición inválida", permanente=True)

    f = Mala()
    t, pausas = tienda(f)
    assert not t.get(DESDE, HASTA).completo and f.llamadas == 1 and pausas == []
