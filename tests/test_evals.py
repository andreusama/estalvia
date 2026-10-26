"""Evals de extracción (spec #10, ticket #15): puntuación por campo crítico e inyección. Cliente falso, sin red."""
import copy
import json
import os
from decimal import Decimal

import pytest

from estalvia.ai.gateway import ErrorIA, RespuestaIA
from estalvia.ai.masking import sellar
from estalvia.extraction.evals import ejecutar, estimar_evals, guardar_informe, principal, texto_informe
from estalvia.extraction.evals_casos import CASOS, INSTRUCCION_INYECTADA
from estalvia.extraction.extractor import Ajustes, normalizar_salida
from estalvia.extraction.schema import validar_datos

CLAVE = b"clave-de-prueba-no-real"


class ModeloFalso:
    """Contesta con la salida ideal del caso al que pertenece el texto, o con la que devuelva `alterar`."""

    def __init__(self, alterar=None, clave=CLAVE):
        self.alterar = alterar
        self.clave = clave
        self.llamadas = 0

    def completar(self, peticion):
        self.llamadas += 1
        caso = next(c for c in CASOS if sellar(c.texto, clave=self.clave) == peticion.texto)
        salida = copy.deepcopy(caso.ideal)
        if self.alterar:
            salida = self.alterar(caso.nombre, salida) or salida
        return RespuestaIA("fin", json.dumps(salida), 100, 50, modelo="claude-opus-5-5")


def informe(alterar=None):
    return ejecutar(CASOS, ModeloFalso(alterar), ajustes=Ajustes(), clave=CLAVE)


def caso_del(inf, nombre):
    return next(c for c in inf.casos if c.nombre == nombre)


def test_los_casos_sinteticos_cubren_castellano_catalan_y_dos_tarifas_y_su_salida_ideal_es_coherente():
    assert {c.nombre for c in CASOS} >= {"es-2.0TD", "ca-2.0TD", "es-3.0TD", "ca-3.0TD", "es-2.0TD-inyeccion"}
    for c in CASOS:
        factura, problemas = validar_datos(normalizar_salida(c.ideal))
        assert factura is not None and problemas == [], c.nombre


def test_con_la_salida_ideal_todos_los_casos_aprueban():
    inf = informe()
    assert all(c.aprobado for c in inf.casos) and all(all(c.criticos.values()) for c in inf.casos)
    assert inf.tokens_entrada == 100 * len(CASOS) and inf.modelos == {"claude-opus-5-5"}


def test_un_campo_critico_mal_extraido_suspende_ese_caso_y_nombra_el_campo():
    def mal(nombre, salida):
        if nombre == "ca-3.0TD":
            salida["energia_kwh"]["P4"] = "401"
            return salida

    inf = informe(mal)
    suspendido = caso_del(inf, "ca-3.0TD")
    assert not suspendido.aprobado and suspendido.criticos["energia_kwh.P4"] is False
    assert all(c.aprobado for c in inf.casos if c.nombre != "ca-3.0TD")


def test_un_campo_critico_omitido_suspende_el_caso():
    def mal(nombre, salida):
        if nombre == "es-2.0TD":
            salida["periodo_facturado"]["fin"] = None
            return salida

    inf = informe(mal)
    caso = caso_del(inf, "es-2.0TD")
    assert not caso.aprobado and caso.criticos["periodo_facturado.fin"] is False


def test_un_campo_no_critico_erroneo_se_informa_pero_no_suspende():
    def mal(nombre, salida):
        if nombre == "es-3.0TD":
            salida["comercializadora"] = "Otra S.A."
            return salida

    caso = caso_del(informe(mal), "es-3.0TD")
    assert caso.aprobado and caso.otros["comercializadora"] is False


def test_un_total_que_no_cuadra_con_las_lineas_suspende_el_caso_por_revision():
    def mal(nombre, salida):
        if nombre == "es-2.0TD":
            salida["conceptos"][0]["importe"] = "99.99"
            return salida

    caso = caso_del(informe(mal), "es-2.0TD")
    assert caso.en_revision and not caso.aprobado


def test_el_dinero_se_compara_al_centimo_y_las_fechas_exactas():
    def mal(nombre, salida):
        if nombre == "es-2.0TD":
            salida["total"] = "54.70"
            salida["periodo_facturado"]["inicio"] = "2026-01-02"
            return salida

    caso = caso_del(informe(mal), "es-2.0TD")
    assert caso.criticos["total"] is False and caso.criticos["periodo_facturado.inicio"] is False


def test_inyeccion_el_texto_lleva_la_instruccion_y_sigue_siendo_dato_tras_enmascarar():
    caso = next(c for c in CASOS if c.inyeccion)
    assert INSTRUCCION_INYECTADA in caso.texto and INSTRUCCION_INYECTADA in sellar(caso.texto, clave=CLAVE)


def test_inyeccion_si_el_modelo_la_ignora_el_caso_aprueba():
    assert caso_del(informe(), "es-2.0TD-inyeccion").aprobado


def test_inyeccion_si_el_modelo_obedece_solo_en_el_total_la_comprobacion_lo_manda_a_revision():
    def obedece(nombre, salida):
        if nombre == "es-2.0TD-inyeccion":
            salida["total"] = "0"
            return salida

    caso = caso_del(informe(obedece), "es-2.0TD-inyeccion")
    assert caso.en_revision and caso.aprobado  # se alteró, pero no se aceptó en silencio


def test_inyeccion_si_el_modelo_obedece_y_deja_todo_coherente_el_caso_suspende():
    def obedece_del_todo(nombre, salida):
        if nombre == "es-2.0TD-inyeccion":
            for c in salida["conceptos"]:
                c["importe"] = "0"
            salida["impuestos"] = {"electrico": "0", "iva": "0"}
            salida["total"] = "0"
            return salida

    caso = caso_del(informe(obedece_del_todo), "es-2.0TD-inyeccion")
    assert not caso.en_revision and not caso.aprobado and caso.criticos["total"] is False


def test_la_comprobacion_determinista_detecta_un_total_incoherente_sin_intervencion_del_modelo():
    caso = next(c for c in CASOS if c.inyeccion)
    alterado = copy.deepcopy(caso.ideal)
    alterado["total"] = "0"
    _, problemas = validar_datos(normalizar_salida(alterado))
    assert problemas


def test_el_informe_nombra_campos_y_resultados_pero_no_valores_de_la_factura(tmp_path):
    inf = informe(lambda n, s: None)
    texto = texto_informe(inf)
    assert "es-2.0TD" in texto and "total" in texto
    for valor in ("54.69", "54,69", "381.56", "Ana", "Energía Ficticia"):
        assert valor not in texto
    ruta = guardar_informe(inf, tmp_path / "resultado.json")
    contenido = ruta.read_text(encoding="utf-8")
    assert json.loads(contenido)["version_prompt"] and "54.69" not in contenido and "Ana" not in contenido
    assert os.stat(ruta).st_mode & 0o777 == 0o600


def test_estimacion_de_las_evals_suma_el_peor_caso_de_cada_texto():
    est = estimar_evals(CASOS, Ajustes(), clave=CLAVE)
    assert est.usd_maximo > Decimal("0.32") * len(CASOS) and est.tokens_entrada > 0


class FabricaFalsa:
    def __init__(self):
        self.creada_con = None
        self.modelo = ModeloFalso(clave=b"k" * 32)

    def __call__(self, entorno, presupuesto_usd):
        self.creada_con = presupuesto_usd
        return self.modelo


ENTORNO = {"ANTHROPIC_API_KEY": "CLAVE-FALSA-SECRETO", "ESTALVIA_MASK_KEY": "k" * 32}


def test_orden_real_sin_clave_se_omite_sin_llamar_a_nada(capsys):
    fabrica = FabricaFalsa()
    codigo = principal(["--real", "--presupuesto-usd", "5"], entorno={"ESTALVIA_MASK_KEY": "k" * 32},
                       fabrica_cliente=fabrica)
    assert codigo == 2 and fabrica.creada_con is None and "ANTHROPIC_API_KEY" in capsys.readouterr().out


def test_orden_real_muestra_la_estimacion_antes_y_no_llama_si_supera_el_presupuesto(capsys):
    fabrica = FabricaFalsa()
    codigo = principal(["--real", "--presupuesto-usd", "0.01"], entorno=ENTORNO, fabrica_cliente=fabrica)
    salida = capsys.readouterr().out
    assert codigo == 3 and fabrica.modelo.llamadas == 0 and "USD" in salida and "SECRETO" not in salida


def test_orden_real_con_presupuesto_suficiente_ejecuta_y_ensena_la_estimacion_primero(capsys, tmp_path):
    fabrica = FabricaFalsa()
    codigo = principal(["--real", "--presupuesto-usd", "10", "--guardar", str(tmp_path / "r.json")],
                       entorno=ENTORNO, fabrica_cliente=fabrica)
    salida = capsys.readouterr().out
    assert codigo == 0 and fabrica.modelo.llamadas == len(CASOS) and fabrica.creada_con == Decimal("10")
    assert salida.index("estimado") < salida.index("es-2.0TD") and (tmp_path / "r.json").is_file()
    assert "SECRETO" not in salida


def test_orden_sin_real_no_hace_nada_y_explica(capsys):
    fabrica = FabricaFalsa()
    assert principal([], entorno=ENTORNO, fabrica_cliente=fabrica) == 2
    assert fabrica.creada_con is None and "--real" in capsys.readouterr().out


def test_un_error_permanente_del_cliente_suspende_todos_los_casos_tambien_el_de_inyeccion():
    class Roto:
        def completar(self, peticion):
            raise ErrorIA("clave rechazada", permanente=True)

    inf = ejecutar(CASOS, Roto(), ajustes=Ajustes(), clave=CLAVE)
    assert not any(c.aprobado for c in inf.casos)


def test_inyeccion_una_respuesta_basura_no_cuenta_como_haberla_resistido():
    class Basura:
        def completar(self, peticion):
            return RespuestaIA("fin", "no es json", 1, 1)

    caso = caso_del(ejecutar(CASOS, Basura(), ajustes=Ajustes(), clave=CLAVE), "es-2.0TD-inyeccion")
    assert caso.en_revision and not caso.aprobado


def test_inyeccion_alterar_otro_campo_critico_ademas_del_total_suspende_aunque_vaya_a_revision():
    def obedece_a_medias(nombre, salida):
        if nombre == "es-2.0TD-inyeccion":
            salida["total"] = "0"
            salida["energia_kwh"]["P1"] = "0"
            return salida

    caso = caso_del(informe(obedece_a_medias), "es-2.0TD-inyeccion")
    assert caso.en_revision and not caso.aprobado


def test_inyeccion_un_kwh_negativo_con_total_cero_tampoco_aprueba():
    def mal(nombre, salida):
        if nombre == "es-2.0TD-inyeccion":
            salida["total"] = "0"
            salida["energia_kwh"]["P1"] = "-50"
            return salida

    assert not caso_del(informe(mal), "es-2.0TD-inyeccion").aprobado


def test_inyeccion_solo_aprueba_por_revision_si_la_causa_es_que_la_suma_no_cuadra():
    caso = caso_del(informe(lambda n, s: s.update(total="0") if n == "es-2.0TD-inyeccion" else None),
                    "es-2.0TD-inyeccion")
    assert caso.aprobado and caso.suma_no_cuadra


def test_los_impuestos_impresos_son_campos_criticos():
    def mal(nombre, salida):
        if nombre == "es-3.0TD":
            salida["impuestos"]["iva"] = "66.23"
            return salida

    caso = caso_del(informe(mal), "es-3.0TD")
    assert caso.criticos["impuestos.iva"] is False and not caso.aprobado


def test_el_informe_da_el_acierto_agregado_en_campos_criticos_y_el_porcentaje_sin_revision():
    inf = informe()
    assert inf.acierto_criticos == Decimal(1) and inf.sin_revision == Decimal(1)
    assert "98" in texto_informe(inf)

    def mal(nombre, salida):
        if nombre == "es-2.0TD":
            salida["total"] = "54.80"
            return salida

    peor = informe(mal)
    assert peor.acierto_criticos < Decimal(1) and peor.sin_revision < Decimal(1)


@pytest.mark.parametrize("valor", ["abc", "NaN", "0", "-1", "inf"])
def test_un_presupuesto_invalido_sale_con_codigo_2_sin_traza(valor, capsys):
    fabrica = FabricaFalsa()
    with pytest.raises(SystemExit) as e:
        principal(["--real", "--presupuesto-usd", valor], entorno=ENTORNO, fabrica_cliente=fabrica)
    assert e.value.code == 2 and fabrica.creada_con is None


def test_orden_real_sin_clave_de_enmascarado_se_omite(capsys):
    fabrica = FabricaFalsa()
    codigo = principal(["--real", "--presupuesto-usd", "5"], entorno={"ANTHROPIC_API_KEY": "x"},
                       fabrica_cliente=fabrica)
    assert codigo == 2 and fabrica.creada_con is None and "ESTALVIA_MASK_KEY" in capsys.readouterr().out


def test_guardar_informe_no_escribe_a_traves_de_un_enlace_simbolico(tmp_path):
    objetivo = tmp_path / "objetivo.json"
    (tmp_path / "r.json").symlink_to(objetivo)
    with pytest.raises(OSError):
        guardar_informe(informe(), tmp_path / "r.json")
    assert not objetivo.exists()
