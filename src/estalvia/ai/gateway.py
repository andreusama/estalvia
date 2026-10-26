"""Cliente de la API de Claude detrás de una interfaz mínima, y lectura de configuración (spec #10, ticket #14).

La IA solo lee: no hay herramientas ni parámetros de muestreo (la API ya no los admite en estos modelos) y la
salida va restringida a un esquema JSON. Ninguna clave se imprime, se guarda en un error ni aparece en un `repr`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol

import anthropic

from estalvia.ai.masking import TextoEnmascarado

BETA_FALLBACKS = "server-side-fallback-2026-07-01"
# USD por millón de tokens (entrada, salida), de la tabla de la skill claude-api. VERIFICAR contra la página de
# precios antes de facturar a un cliente. Un modelo que no está aquí no se estima ni se llama.
PRECIOS_USD_POR_MILLON = {
    "claude-opus-5-5": (Decimal(4), Decimal(20)),
    "claude-sonnet-5-5": (Decimal(2), Decimal(10)),
}
LONGITUD_MINIMA_CLAVE_ENMASCARADO = 16


class ErrorIA(Exception):
    """Fallo al llamar a la IA. El mensaje no lleva texto de la factura ni claves."""

    def __init__(self, mensaje: str, permanente: bool = False):
        super().__init__(mensaje)
        self.permanente = permanente


class ErrorConfig(Exception):
    """Falta o es inválida una variable de configuración."""


Esfuerzo = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class Peticion:
    """Lo que se envía a la IA. El texto de la factura es un campo aparte y solo admite texto enmascarado; el
    `repr` no lo muestra (acabaría en registros y trazas)."""
    modelo: str
    esfuerzo: Esfuerzo
    max_tokens: int
    sistema: str
    texto: TextoEnmascarado = field(repr=False)
    esquema: dict = field(repr=False)

    def __post_init__(self):
        if not isinstance(self.texto, TextoEnmascarado):
            raise TypeError("el texto debe estar enmascarado: crear con sellar() antes de enviarlo a la IA")

    @property
    def usuario(self) -> str:
        return f"<factura>\n{self.texto}\n</factura>"


@dataclass(frozen=True)
class RespuestaIA:
    parada: Literal["fin", "rechazo", "truncada"]
    texto: str = field(repr=False)
    tokens_entrada: int
    tokens_salida: int
    motivo: str | None = None
    modelo: str | None = None  # el que contestó: con `fallbacks` puede no ser el pedido


class ClienteIA(Protocol):
    def completar(self, peticion: Peticion) -> RespuestaIA: ...


@dataclass(frozen=True)
class Estimacion:
    tokens_entrada: int
    usd_maximo: Decimal  # peor caso: la entrada estimada más todo `max_tokens` de salida (incluye el razonamiento)


def estimar_coste(p: Peticion) -> Estimacion:
    """Cota superior sin llamar a la API: 1 token por cada 2 caracteres (por encima de lo habitual)."""
    if p.modelo not in PRECIOS_USD_POR_MILLON:
        raise ErrorIA(f"no hay precio conocido para el modelo {p.modelo}: no se estima ni se llama", permanente=True)
    precio_entrada, precio_salida = PRECIOS_USD_POR_MILLON[p.modelo]
    tokens = (len(p.sistema) + len(p.usuario) + 1) // 2
    usd = (Decimal(tokens) * precio_entrada + Decimal(p.max_tokens) * precio_salida) / Decimal(1_000_000)
    return Estimacion(tokens, usd)


class ClienteAnthropic:
    def __init__(self, sdk: anthropic.Anthropic, *, presupuesto_usd: Decimal):
        self._sdk = sdk
        self._presupuesto = presupuesto_usd
        self._comprometido = Decimal(0)  # suma de los peores casos de las llamadas hechas

    def __repr__(self) -> str:
        return "ClienteAnthropic(<oculto>)"

    @classmethod
    def desde_entorno(cls, entorno: dict[str, str] | None = None, *, presupuesto_usd: Decimal) -> ClienteAnthropic:
        entorno = leer_env() if entorno is None else entorno
        clave = entorno.get("ANTHROPIC_API_KEY")
        if not clave:
            raise ErrorConfig("falta ANTHROPIC_API_KEY (ponla en el fichero .env, nunca en el código ni el chat)")
        return cls(anthropic.Anthropic(api_key=clave, max_retries=0), presupuesto_usd=presupuesto_usd)

    def completar(self, p: Peticion) -> RespuestaIA:
        estimacion = estimar_coste(p)
        if self._comprometido + estimacion.usd_maximo > self._presupuesto:
            raise ErrorIA(f"el coste máximo estimado ({estimacion.usd_maximo} USD) supera el presupuesto aprobado "
                          f"({self._presupuesto} USD, ya comprometidos {self._comprometido})", permanente=True)
        self._comprometido += estimacion.usd_maximo  # aunque la llamada falle: no se sabe lo que se facturó
        try:
            r = self._sdk.beta.messages.create(
                model=p.modelo, max_tokens=p.max_tokens, system=p.sistema,
                messages=[{"role": "user", "content": p.usuario}],
                output_config={"effort": p.esfuerzo, "format": {"type": "json_schema", "schema": p.esquema}},
                fallbacks="default", betas=[BETA_FALLBACKS],
            )
        except anthropic.APIStatusError as e:  # sin el mensaje del SDK: puede citar cabeceras o claves
            raise ErrorIA(f"error de la API ({e.status_code})",
                          permanente=e.status_code in (400, 401, 403, 404, 413, 422)) from None
        except anthropic.APIConnectionError:
            raise ErrorIA("sin conexión con la API", permanente=False) from None
        entrada, salida = r.usage.input_tokens, r.usage.output_tokens
        if r.stop_reason == "refusal":
            detalle = getattr(r, "stop_details", None)
            return RespuestaIA("rechazo", "", entrada, salida, motivo=getattr(detalle, "category", None),
                               modelo=r.model)
        texto = "".join(b.text for b in r.content if b.type == "text")
        return RespuestaIA("fin" if r.stop_reason in ("end_turn", "stop_sequence") else "truncada",
                           texto, entrada, salida, modelo=r.model)


class Entorno(dict):
    """Variables de configuración; el `repr` no muestra los valores (llevan claves)."""

    def __repr__(self) -> str:
        return f"Entorno(<{len(self)} variables ocultas>)"

    __str__ = __repr__


def leer_env(ruta: str | Path = ".env", *, entorno: dict[str, str] | None = None) -> dict[str, str]:
    """Variables del fichero `.env` (si existe) con las del entorno por encima."""
    entorno = dict(os.environ) if entorno is None else entorno
    valores: dict[str, str] = {}
    ruta = Path(ruta)
    if ruta.is_file():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            nombre, valor = (x.strip() for x in linea.split("=", 1))
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
                valor = valor[1:-1]
            valores[nombre] = valor
    return Entorno({**valores, **entorno})


def clave_enmascarado(entorno: dict[str, str]) -> bytes:
    valor = entorno.get("ESTALVIA_MASK_KEY", "")
    if not valor:
        raise ErrorConfig("falta ESTALVIA_MASK_KEY (una cadena aleatoria larga en .env)")
    if len(valor.encode()) < LONGITUD_MINIMA_CLAVE_ENMASCARADO:
        raise ErrorConfig(f"ESTALVIA_MASK_KEY es demasiado corta (mínimo {LONGITUD_MINIMA_CLAVE_ENMASCARADO} bytes)")
    return valor.encode()
