"""Adaptador de la API de Claude, entorno y estimación de coste (spec #10, ticket #14). Sin red, sin clave real."""
from decimal import Decimal
from types import SimpleNamespace

import anthropic
import httpx2 as httpx  # el SDK 2.x usa httpx2
import pytest

from estalvia.ai.gateway import (
    ClienteAnthropic,
    ErrorConfig,
    ErrorIA,
    Peticion,
    clave_enmascarado,
    estimar_coste,
    leer_env,
)

PETICION = Peticion(modelo="claude-opus-5-5", esfuerzo="medium", max_tokens=16000, sistema="s", usuario="u",
                    esquema={"type": "object", "additionalProperties": False, "properties": {}, "required": []})


class SdkFalso:
    def __init__(self, respuesta=None, error=None):
        self.llamadas: list[dict] = []
        self._respuesta, self._error = respuesta, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.llamadas.append(kw)
        if self._error:
            raise self._error
        return self._respuesta


def respuesta(stop="end_turn", bloques=None, **extra):
    bloques = bloques if bloques is not None else [SimpleNamespace(type="text", text='{"a": 1}')]
    return SimpleNamespace(stop_reason=stop, content=bloques, usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                           **extra)


def cliente(sdk, presupuesto="1"):
    return ClienteAnthropic(sdk, presupuesto_usd=Decimal(presupuesto))


def test_la_peticion_no_lleva_parametros_de_muestreo_ni_tool_choice_y_pide_esfuerzo_esquema_y_fallbacks():
    sdk = SdkFalso(respuesta())
    cliente(sdk).completar(PETICION)
    kw = sdk.llamadas[0]
    assert not {"temperature", "top_p", "top_k", "tool_choice", "thinking", "tools"} & set(kw)
    assert kw["model"] == "claude-opus-5-5" and kw["max_tokens"] == 16000
    assert kw["output_config"]["effort"] == "medium"
    assert kw["output_config"]["format"] == {"type": "json_schema", "schema": PETICION.esquema}
    assert kw["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in kw["betas"]
    assert kw["system"] == "s" and kw["messages"] == [{"role": "user", "content": "u"}]


def test_respuesta_normal_devuelve_el_texto_y_el_uso_ignorando_bloques_de_razonamiento():
    bloques = [SimpleNamespace(type="thinking", thinking="..."), SimpleNamespace(type="text", text="{}")]
    r = cliente(SdkFalso(respuesta(bloques=bloques))).completar(PETICION)
    assert (r.parada, r.texto, r.tokens_entrada, r.tokens_salida) == ("fin", "{}", 10, 5)


def test_rechazo_y_truncado_se_distinguen_antes_de_leer_el_contenido():
    detalle = SimpleNamespace(category="cyber")
    r = cliente(SdkFalso(respuesta("refusal", bloques=[], stop_details=detalle))).completar(PETICION)
    assert r.parada == "rechazo" and r.motivo == "cyber" and r.texto == ""
    r = cliente(SdkFalso(respuesta("max_tokens"))).completar(PETICION)
    assert r.parada == "truncada"


def test_rechazo_sin_detalles_no_falla():
    r = cliente(SdkFalso(respuesta("refusal", bloques=[]))).completar(PETICION)
    assert r.parada == "rechazo" and r.motivo is None


def test_estimacion_de_coste_peor_caso_con_precios_conocidos():
    p = Peticion(modelo="claude-opus-5-5", esfuerzo="medium", max_tokens=16000, sistema="a" * 1000,
                 usuario="b" * 3000, esquema={})
    e = estimar_coste(p)
    assert e.tokens_entrada == 2000 and e.usd_maximo == Decimal("0.328")


def test_modelo_sin_precio_conocido_no_se_estima_ni_se_inventa():
    p = Peticion(modelo="modelo-desconocido", esfuerzo="medium", max_tokens=1, sistema="", usuario="", esquema={})
    with pytest.raises(ErrorIA, match="precio"):
        estimar_coste(p)


def test_sin_presupuesto_suficiente_no_se_llama_a_la_api():
    sdk = SdkFalso(respuesta())
    with pytest.raises(ErrorIA, match="presupuesto") as e:
        cliente(sdk, presupuesto="0.10").completar(PETICION)
    assert e.value.permanente and sdk.llamadas == []


def test_errores_de_la_api_se_clasifican_sin_filtrar_la_clave():
    req = httpx.Request("POST", "https://api.invalid/v1/messages")
    auth = anthropic.AuthenticationError("sk-ant-SECRETO rechazada", response=httpx.Response(401, request=req),
                                         body=None)
    with pytest.raises(ErrorIA) as e:
        cliente(SdkFalso(error=auth)).completar(PETICION)
    assert e.value.permanente and "SECRETO" not in str(e.value)
    red = anthropic.APIConnectionError(request=req)
    with pytest.raises(ErrorIA) as e:
        cliente(SdkFalso(error=red)).completar(PETICION)
    assert not e.value.permanente
    limite = anthropic.RateLimitError("demasiadas", response=httpx.Response(429, request=req), body=None)
    with pytest.raises(ErrorIA) as e:
        cliente(SdkFalso(error=limite)).completar(PETICION)
    assert not e.value.permanente


def test_desde_entorno_usa_la_clave_sin_mostrarla_y_falla_claro_si_falta():
    c = ClienteAnthropic.desde_entorno({"ANTHROPIC_API_KEY": "sk-ant-SECRETO"}, presupuesto_usd=Decimal("1"))
    assert "SECRETO" not in repr(c) and "SECRETO" not in str(vars(c).get("presupuesto_usd"))
    with pytest.raises(ErrorConfig, match="ANTHROPIC_API_KEY"):
        ClienteAnthropic.desde_entorno({}, presupuesto_usd=Decimal("1"))


def test_leer_env_analiza_el_fichero_y_el_entorno_manda(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# comentario\nA=1\nB="dos"\n\nC = tres \nmal formada\n', encoding="utf-8")
    assert leer_env(f, entorno={}) == {"A": "1", "B": "dos", "C": "tres"}
    assert leer_env(f, entorno={"A": "9"})["A"] == "9"
    assert leer_env(tmp_path / "no-existe", entorno={}) == {}


def test_clave_de_enmascarado_se_lee_del_entorno_y_exige_longitud_minima():
    assert clave_enmascarado({"ESTALVIA_MASK_KEY": "x" * 32}) == b"x" * 32
    with pytest.raises(ErrorConfig, match="ESTALVIA_MASK_KEY"):
        clave_enmascarado({})
    with pytest.raises(ErrorConfig, match="corta"):
        clave_enmascarado({"ESTALVIA_MASK_KEY": "corta"})
