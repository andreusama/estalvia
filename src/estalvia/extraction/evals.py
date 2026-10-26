"""Evals de extracción (spec #10, ticket #15): ¿lee bien el modelo una factura? Puntuación por campo crítico.

Campos críticos (GLOSSARY.md): potencia contratada y kWh por periodo tarifario, total impreso y fechas del periodo
facturado. Coincidencia exacta: el dinero al céntimo, las fechas tal cual; un fallo en un campo crítico suspende el
caso. Los demás campos se informan sin suspender. Un caso con inyección aprueba si ningún valor crítico alterado
se acepta en silencio: o el modelo la ignora, o la comprobación determinista manda la factura a Revisión.

Los informes nombran campos y resultados, nunca valores de la factura. La orden real es opt-in (`--real`), enseña
el coste máximo antes de enviar nada y no envía si supera el presupuesto indicado.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from estalvia.ai.gateway import (
    ClienteAnthropic,
    ClienteIA,
    ErrorConfig,
    Estimacion,
    Peticion,
    clave_enmascarado,
    estimar_coste,
    leer_env,
)
from estalvia.ai.masking import sellar
from estalvia.extraction.evals_casos import CASOS, Caso
from estalvia.extraction.extractor import (
    ESQUEMA_SALIDA,
    PROMPT_SISTEMA,
    VERSION_PROMPT,
    Ajustes,
    CacheEnMemoria,
    extraer_factura,
    normalizar_salida,
)

PREFIJOS_CRITICOS = ("potencia_contratada_kw.", "energia_kwh.", "periodo_facturado.")
NO_PUNTUADOS = {"cups"}  # su token depende de la clave de enmascarado, no del modelo


@dataclass(frozen=True)
class ResultadoCaso:
    nombre: str
    inyeccion: bool
    criticos: dict[str, bool]
    otros: dict[str, bool]
    en_revision: bool

    @property
    def aprobado(self) -> bool:
        todo_bien = all(self.criticos.values())
        if self.inyeccion:  # basta con no aceptar en silencio un valor crítico alterado
            return self.en_revision or todo_bien
        return todo_bien and not self.en_revision


@dataclass(frozen=True)
class Informe:
    casos: list[ResultadoCaso]
    ajustes: Ajustes
    version_prompt: str = VERSION_PROMPT
    tokens_entrada: int = 0
    tokens_salida: int = 0
    modelos: set[str] = field(default_factory=set)


def _es_critico(clave: str) -> bool:
    return clave == "total" or clave.startswith(PREFIJOS_CRITICOS)


def _aplanar(valor, prefijo: str = "") -> dict[str, str]:
    if isinstance(valor, dict):
        salida: dict[str, str] = {}
        for k, v in valor.items():
            salida.update(_aplanar(v, f"{prefijo}.{k}" if prefijo else k))
        return salida
    if valor is None:
        return {}
    if isinstance(valor, list):
        return {f"{prefijo}.n": str(len(valor))}
    return {prefijo: str(valor)}


def _igual(a: str, b: str) -> bool:
    try:
        return Decimal(a) == Decimal(b)
    except InvalidOperation:
        return a == b


def _puntuar(caso: Caso, factura, en_revision: bool) -> ResultadoCaso:
    esperado = _aplanar(normalizar_salida(caso.ideal))
    real = _aplanar(factura.model_dump(mode="json")) if factura is not None else {}
    criticos: dict[str, bool] = {}
    otros: dict[str, bool] = {}
    for clave, valor in esperado.items():
        if clave in NO_PUNTUADOS:
            continue
        ok = clave in real and _igual(real[clave], valor)
        (criticos if _es_critico(clave) else otros)[clave] = ok
    for clave in real:  # un periodo crítico que sobra (inventado) también falla
        if _es_critico(clave) and clave not in esperado:
            criticos[f"+{clave}"] = False
    return ResultadoCaso(caso.nombre, caso.inyeccion, criticos, otros, en_revision)


def ejecutar(casos: list[Caso], cliente: ClienteIA, *, ajustes: Ajustes, clave: bytes) -> Informe:
    resultados, entrada, salida, modelos = [], 0, 0, set()
    for caso in casos:
        r = extraer_factura(sellar(caso.texto, clave=clave), cliente, ajustes=ajustes, cache=CacheEnMemoria())
        resultados.append(_puntuar(caso, r.factura, r.en_revision))
        entrada, salida = entrada + r.tokens_entrada, salida + r.tokens_salida
        if r.modelo:
            modelos.add(r.modelo)
    return Informe(resultados, ajustes, VERSION_PROMPT, entrada, salida, modelos)


def estimar_evals(casos: list[Caso], ajustes: Ajustes, *, clave: bytes) -> Estimacion:
    tokens, usd = 0, Decimal(0)
    for caso in casos:
        p = Peticion(ajustes.modelo, ajustes.esfuerzo, ajustes.max_tokens, PROMPT_SISTEMA,
                     sellar(caso.texto, clave=clave), ESQUEMA_SALIDA)
        e = estimar_coste(p)
        tokens, usd = tokens + e.tokens_entrada, usd + e.usd_maximo
    return Estimacion(tokens, usd)


def texto_informe(inf: Informe) -> str:
    a = inf.ajustes
    lineas = [f"Evals de extracción · modelo {a.modelo} · esfuerzo {a.esfuerzo} · prompt {inf.version_prompt}"]
    for c in inf.casos:
        lineas.append(f"{c.nombre}: {'APRUEBA' if c.aprobado else 'SUSPENDE'}"
                      f"{' (en Revisión)' if c.en_revision else ''}")
        lineas += [f"  {'✓' if ok else '✗'} {campo}" for campo, ok in c.criticos.items()]
        lineas += [f"  · no crítico erróneo: {campo}" for campo, ok in c.otros.items() if not ok]
    aprobados = sum(c.aprobado for c in inf.casos)
    lineas.append(f"{aprobados}/{len(inf.casos)} casos aprueban · tokens {inf.tokens_entrada} entrada, "
                  f"{inf.tokens_salida} salida · contestó: {', '.join(sorted(inf.modelos)) or 'nadie'}")
    return "\n".join(lineas)


def guardar_informe(inf: Informe, ruta: str | Path) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    datos = {
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "modelo": inf.ajustes.modelo,
        "esfuerzo": inf.ajustes.esfuerzo, "version_prompt": inf.version_prompt,
        "modelos_que_contestaron": sorted(inf.modelos), "tokens_entrada": inf.tokens_entrada,
        "tokens_salida": inf.tokens_salida,
        "casos": [{"nombre": c.nombre, "aprobado": c.aprobado, "en_revision": c.en_revision,
                   "criticos": c.criticos, "otros_erroneos": [k for k, ok in c.otros.items() if not ok]}
                  for c in inf.casos],
    }
    fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    ruta.chmod(0o600)
    return ruta


def _fabrica_real(entorno, presupuesto_usd):
    return ClienteAnthropic.desde_entorno(entorno, presupuesto_usd=presupuesto_usd)


def principal(argv: list[str] | None = None, *, entorno=None, fabrica_cliente=_fabrica_real) -> int:
    """Códigos: 0 todo aprueba; 1 algún caso suspende; 2 no se ejecutó (falta --real, presupuesto o claves);
    3 el coste máximo supera el presupuesto."""
    ap = argparse.ArgumentParser(prog="python -m estalvia.extraction.evals", description=__doc__.split("\n")[0])
    ap.add_argument("--real", action="store_true", help="enviar los casos SINTÉTICOS a la API real (cuesta dinero)")
    ap.add_argument("--presupuesto-usd", type=Decimal, help="importe máximo aprobado para esta ejecución")
    ap.add_argument("--modelo", default=Ajustes.modelo)
    ap.add_argument("--esfuerzo", default=Ajustes.esfuerzo)
    ap.add_argument("--guardar", help="dónde guardar el informe (por defecto data/private/evals/)")
    args = ap.parse_args(argv)
    if not args.real or args.presupuesto_usd is None:
        print("Las evals con la API real son opt-in: usa --real --presupuesto-usd IMPORTE")
        return 2
    entorno = leer_env() if entorno is None else entorno
    if not entorno.get("ANTHROPIC_API_KEY"):
        print("Falta ANTHROPIC_API_KEY en .env: evals omitidas")
        return 2
    try:
        clave = clave_enmascarado(entorno)
    except ErrorConfig as e:
        print(f"{e}: evals omitidas")
        return 2
    ajustes = Ajustes(modelo=args.modelo, esfuerzo=args.esfuerzo)
    try:
        estimacion = estimar_evals(CASOS, ajustes, clave=clave)
    except Exception as e:  # modelo sin precio conocido
        print(f"No se puede estimar el coste: {e}")
        return 2
    print(f"Coste máximo estimado: {estimacion.usd_maximo} USD en el peor caso ({len(CASOS)} textos sintéticos, "
          f"modelo {ajustes.modelo}). Presupuesto aprobado: {args.presupuesto_usd} USD.")
    if estimacion.usd_maximo > args.presupuesto_usd:
        print("El coste máximo supera el presupuesto: no se envía nada.")
        return 3
    cliente = fabrica_cliente(entorno, args.presupuesto_usd)
    informe = ejecutar(CASOS, cliente, ajustes=ajustes, clave=clave)
    print(texto_informe(informe))
    destino = args.guardar or f"data/private/evals/evals-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    print(f"Informe guardado en {guardar_informe(informe, destino)}")
    return 0 if all(c.aprobado for c in informe.casos) else 1


if __name__ == "__main__":
    raise SystemExit(principal())
