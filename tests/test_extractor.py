"""Pasarela de extracción con un cliente de IA falso (spec #10, ticket #14). Solo datos sintéticos."""
import json
from decimal import Decimal

import pytest

from estalvia.ai.gateway import ErrorIA, Peticion, RespuestaIA
from estalvia.ai.masking import TextoEnmascarado, sellar
from estalvia.extraction.extractor import (
    ESQUEMA_SALIDA,
    PERIODOS,
    Ajustes,
    CacheEnDisco,
    CacheEnMemoria,
    extraer_factura,
    normalizar_salida,
)
from estalvia.extraction.schema import FacturaExtraida

CLAVE = b"clave-de-prueba-no-real"
TEXTO = sellar("Titular: Ana Ejemplo\nCUPS: ES0000000000000000AA\nTotal factura: 127,05 €", clave=CLAVE)


def por_periodo(**valores):
    return {p: valores.get(p) for p in PERIODOS}


def salida(**cambios):
    base = {
        "comercializadora": "X", "cups": "[CUPS:abc123]", "tarifa_acceso": "2.0TD", "modalidad_precio": "fijo",
        "periodo_facturado": {"inicio": "2026-01-01", "fin": "2026-01-31"},
        "potencia_contratada_kw": por_periodo(P1="4.4", P2="4.4"),
        "potencia_maxima_kw": por_periodo(), "energia_kwh": por_periodo(P1="50", P2="60", P3="90"),
        "energia_reactiva_kvarh": por_periodo(), "lecturas_contador": None, "desglose_regulado": None,
        "conceptos": [{"nombre": "energia", "cantidad": "200", "precio": "0.5", "importe": "100"}],
        "impuestos": {"electrico": "5", "iva": "22.05"}, "total": "127.05",
    }
    base.update(cambios)
    return base


def ok(texto=None, **cambios):
    return RespuestaIA("fin", texto if texto is not None else json.dumps(salida(**cambios)), 100, 50)


class ClienteFalso:
    """Devuelve (o lanza) lo que se le da, en orden; registra cada petición."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.peticiones: list[Peticion] = []

    def completar(self, peticion):
        self.peticiones.append(peticion)
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def extraer(cliente, texto=TEXTO, cache=None, **kw):
    return extraer_factura(texto, cliente, ajustes=Ajustes(), cache=cache or CacheEnMemoria(), **kw)


def test_respuesta_valida_da_factura_sin_problemas_en_una_llamada():
    cliente = ClienteFalso(ok())
    r = extraer(cliente)
    assert isinstance(r.factura, FacturaExtraida) and r.problemas == [] and not r.en_revision
    assert r.factura.total == Decimal("127.05") and len(cliente.peticiones) == 1


def test_los_nulos_del_esquema_se_convierten_en_campos_ausentes():
    r = extraer(ClienteFalso(ok()))
    assert r.factura.lecturas_contador is None and r.factura.desglose_regulado is None
    assert set(r.factura.energia_kwh) == {"P1", "P2", "P3"} and r.factura.potencia_maxima_kw == {}


def test_normalizar_salida_quita_nulos_y_periodos_vacios():
    d = normalizar_salida(salida(lecturas_contador=por_periodo(P1={"inicial": "1", "final": "2"})))
    assert d["lecturas_contador"] == {"P1": {"inicial": "1", "final": "2"}}
    assert "potencia_maxima_kw" not in d or d["potencia_maxima_kw"] == {}


def test_json_mal_formado_reintenta_una_vez_y_acepta_la_segunda():
    cliente = ClienteFalso(ok("esto no es json"), ok())
    r = extraer(cliente)
    assert not r.en_revision and len(cliente.peticiones) == 2


def test_dos_respuestas_malas_van_a_revision_sin_tercer_intento():
    cliente = ClienteFalso(ok("{"), ok(json.dumps({"comercializadora": "X"})))
    r = extraer(cliente)
    assert r.en_revision and r.factura is None and len(cliente.peticiones) == 2
    assert any("total" in p for p in r.problemas)


def test_los_motivos_de_revision_no_repiten_el_texto_de_la_respuesta():
    r = extraer(ClienteFalso(ok("Ana Ejemplo no es json"), ok("Ana Ejemplo otra vez")))
    assert r.en_revision and "Ana" not in " ".join(r.problemas)


def test_fallo_transitorio_reintenta_y_fallo_permanente_no():
    cliente = ClienteFalso(ErrorIA("red caída", permanente=False), ok())
    assert not extraer(cliente).en_revision and len(cliente.peticiones) == 2
    cliente = ClienteFalso(ErrorIA("clave rechazada", permanente=True), ok())
    r = extraer(cliente)
    assert r.en_revision and len(cliente.peticiones) == 1 and "clave rechazada" in " ".join(r.problemas)


def test_rechazo_va_a_revision_con_el_motivo_y_sin_reintento():
    cliente = ClienteFalso(RespuestaIA("rechazo", "", 100, 0, motivo="cyber"), ok())
    r = extraer(cliente)
    assert r.en_revision and "cyber" in " ".join(r.problemas) and len(cliente.peticiones) == 1


def test_respuesta_truncada_reintenta_y_luego_va_a_revision():
    cliente = ClienteFalso(RespuestaIA("truncada", '{"a"', 100, 16000), RespuestaIA("truncada", "{", 100, 16000))
    r = extraer(cliente)
    assert r.en_revision and len(cliente.peticiones) == 2


def test_fallo_de_comprobacion_determinista_va_a_revision_sin_reintento():
    cliente = ClienteFalso(ok(total="130.00"), ok())
    r = extraer(cliente)
    assert r.en_revision and r.factura is not None and len(cliente.peticiones) == 1
    assert "127.05" in r.problemas[0]


def test_cache_sirve_el_mismo_texto_sin_llamar_otra_vez():
    cliente, cache = ClienteFalso(ok(), ok()), CacheEnMemoria()
    extraer(cliente, cache=cache)
    extraer(cliente, cache=cache)
    assert len(cliente.peticiones) == 1
    otro = sellar(str(TEXTO) + " distinto", clave=CLAVE)
    extraer(cliente, texto=otro, cache=cache)
    assert len(cliente.peticiones) == 2


def test_la_clave_de_cache_depende_del_modelo_y_del_esfuerzo():
    cliente, cache = ClienteFalso(ok(), ok(), ok()), CacheEnMemoria()
    extraer_factura(TEXTO, cliente, ajustes=Ajustes(modelo="claude-opus-5-5"), cache=cache)
    extraer_factura(TEXTO, cliente, ajustes=Ajustes(modelo="claude-sonnet-5-5"), cache=cache)
    extraer_factura(TEXTO, cliente, ajustes=Ajustes(esfuerzo="high"), cache=cache)
    assert len(cliente.peticiones) == 3


def test_los_fallos_no_se_guardan_en_cache():
    cliente, cache = ClienteFalso(ok("{"), ok("{"), ok()), CacheEnMemoria()
    assert extraer(cliente, cache=cache).en_revision
    assert not extraer(cliente, cache=cache).en_revision
    assert len(cliente.peticiones) == 3


def test_cache_en_disco_persiste_entre_instancias_con_permisos_600(tmp_path):
    cliente = ClienteFalso(ok())
    extraer(cliente, cache=CacheEnDisco(tmp_path / "cache"))
    extraer(cliente, cache=CacheEnDisco(tmp_path / "cache"))
    assert len(cliente.peticiones) == 1
    ficheros = list((tmp_path / "cache").iterdir())
    assert len(ficheros) == 1 and ficheros[0].stat().st_mode & 0o777 == 0o600


def test_solo_texto_enmascarado_llega_a_la_pasarela():
    with pytest.raises(TypeError, match="enmascar"):
        extraer(ClienteFalso(ok()), texto="Titular: Ana Ejemplo")
    with pytest.raises(TypeError):
        TextoEnmascarado("Titular: Ana Ejemplo")


def test_la_peticion_lleva_el_texto_enmascarado_y_una_instruccion_de_tratarlo_como_datos():
    cliente = ClienteFalso(ok())
    extraer(cliente)
    p = cliente.peticiones[0]
    assert "Ana" not in p.usuario and "ES0000000000000000AA" not in p.usuario
    assert str(TEXTO) in p.usuario
    assert "datos" in p.sistema.lower() and "instrucciones" in p.sistema.lower()
    assert p.esquema["additionalProperties"] is False


def _uniones(esquema) -> int:
    """Nodos con `anyOf` o `type` en lista: la API admite como mucho 16 y rechaza la lista junto a `enum`."""
    if isinstance(esquema, dict):
        aqui = int("anyOf" in esquema or isinstance(esquema.get("type"), list))
        return aqui + sum(_uniones(v) for v in esquema.values())
    if isinstance(esquema, list):
        return sum(_uniones(v) for v in esquema)
    return 0


def test_el_esquema_no_tiene_campos_anulables_porque_la_api_limita_las_uniones():
    assert _uniones(ESQUEMA_SALIDA) == 0
    tarifa = ESQUEMA_SALIDA["properties"]["tarifa_acceso"]
    assert tarifa == {"type": "string", "enum": ["2.0TD", "3.0TD", "6.1TD", "otra", ""]}


def test_cadena_vacia_significa_no_impreso_y_se_trata_como_campo_ausente():
    d = normalizar_salida(salida(lecturas_contador=por_periodo(P1={"inicial": "", "final": ""}), cups="",
                                 desglose_regulado=[]))
    assert "lecturas_contador" not in d and "cups" not in d and "desglose_regulado" not in d
    sin_total = ok(total="")
    r = extraer(ClienteFalso(sin_total, sin_total))
    assert r.en_revision


def test_un_concepto_con_importe_nulo_va_a_revision_en_lugar_de_inventarse():
    mal = [{"nombre": "energia", "cantidad": "200", "precio": "0.5", "importe": ""}]
    r = extraer(ClienteFalso(ok(conceptos=mal), ok(conceptos=mal)))
    assert r.en_revision and any("importe" in p for p in r.problemas)


def test_el_resultado_registra_el_modelo_que_contesto_y_su_repr_no_muestra_la_factura():
    r = extraer(ClienteFalso(RespuestaIA("fin", json.dumps(salida()), 100, 50, modelo="claude-opus-4-8")))
    assert r.modelo == "claude-opus-4-8" and "127.05" not in repr(r)


def test_cache_en_disco_no_escribe_a_traves_de_enlaces_simbolicos(tmp_path):
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    (tmp_path / "cache").symlink_to(fuera)
    with pytest.raises(OSError):
        CacheEnDisco(tmp_path / "cache").set("k", "x")
    assert list(fuera.iterdir()) == []


def test_cache_en_disco_corrige_permisos_de_un_fichero_existente(tmp_path):
    carpeta = tmp_path / "cache"
    carpeta.mkdir()
    (carpeta / "k.json").write_text("viejo")
    (carpeta / "k.json").chmod(0o644)
    CacheEnDisco(carpeta).set("k", "nuevo")
    assert (carpeta / "k.json").read_text() == "nuevo" and (carpeta / "k.json").stat().st_mode & 0o777 == 0o600


def test_una_entrada_de_cache_corrupta_se_ignora_y_se_vuelve_a_pedir():
    cache = CacheEnMemoria()
    cliente = ClienteFalso(ok())
    extraer(ClienteFalso(ok()), cache=cache)
    clave = next(iter(cache._datos))
    cache._datos[clave] = "{ corrupto"
    r = extraer(cliente, cache=cache)
    assert not r.en_revision and len(cliente.peticiones) == 1


def test_el_esquema_de_salida_coincide_con_el_modelo_y_con_la_salida_de_ejemplo():
    propiedades = set(ESQUEMA_SALIDA["properties"])
    assert propiedades == set(salida()) and propiedades <= set(FacturaExtraida.model_fields)
    assert set(ESQUEMA_SALIDA["required"]) == propiedades and ESQUEMA_SALIDA["additionalProperties"] is False
    assert {"confianza_campos", "modalidad_precio"} & propiedades == {"modalidad_precio"}
