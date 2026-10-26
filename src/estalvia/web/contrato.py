"""Datos del contrato que imprime la factura (tarifa, potencia, precios, periodo facturado) desde un YAML local.

El fichero vive fuera del repositorio y lo indica `ESTALVIA_CONTRATO` en `.env`; más adelante lo rellenará la
extracción de facturas. Los importes se escriben como texto o entero, nunca como decimal de coma flotante.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from estalvia.analysis.nucleo import PrecioContrato
from estalvia.engine.calc import Periodo, SiteParams


class ErrorContrato(ValueError):
    """El contrato no se puede leer; el mensaje dice el campo, nunca su valor."""


@dataclass(frozen=True)
class Contrato:
    site: SiteParams
    precios: PrecioContrato
    periodo: Periodo


def _decimal(valor, campo: str) -> Decimal:
    if isinstance(valor, bool) or not isinstance(valor, (str, int)):
        raise ErrorContrato(f"{campo}: escribir el número como texto, por ejemplo \"0.15\"")
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        raise ErrorContrato(f"{campo}: no es un número") from None


def _por_periodo(datos, campo: str) -> dict[str, Decimal]:
    if not isinstance(datos, dict) or not datos:
        raise ErrorContrato(f"{campo}: falta o no es un diccionario por periodo")
    return {str(p): _decimal(v, f"{campo}.{p}") for p, v in datos.items()}


def cargar_contrato(ruta: str | Path) -> Contrato:
    try:
        crudo = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        raise ErrorContrato("no se pudo leer el fichero del contrato") from None
    if not isinstance(crudo, dict):
        raise ErrorContrato("el contrato debe ser un diccionario")
    try:
        precios = crudo["precios"]
        periodo = crudo["periodo"]
        inicio, fin = periodo["inicio"], periodo["fin"]
        if not isinstance(inicio, date) or not isinstance(fin, date):
            raise ErrorContrato("periodo: las fechas deben ser AAAA-MM-DD")
        site = SiteParams(str(crudo["tarifa"]), _por_periodo(crudo["potencia_contratada_kw"], "potencia_contratada_kw"),
                          ie_uso=str(crudo.get("ie_uso", "profesional")),
                          aplica_bono_social=bool(crudo.get("aplica_bono_social", False)),
                          alquiler_importe=(_decimal(crudo["alquiler_importe"], "alquiler_importe")
                                            if "alquiler_importe" in crudo else None))
        return Contrato(site, PrecioContrato(_por_periodo(precios["energia_eur_kwh"], "precios.energia_eur_kwh"),
                                             _por_periodo(precios["potencia_eur_kw_anio"],
                                                          "precios.potencia_eur_kw_anio")),
                        Periodo(inicio, fin))
    except KeyError as e:
        raise ErrorContrato(f"falta el campo {e.args[0]}") from None
    except TypeError:
        raise ErrorContrato("el contrato tiene una estructura inesperada") from None
