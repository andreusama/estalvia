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
from estalvia.extraction.schema import PERIODOS_ENERGIA, PERIODOS_POTENCIA

MAXIMO = Decimal("1000000")  # tope de cordura para evitar desbordes; no es un dato regulatorio
DIAS_MAXIMOS = 366


class ErrorContrato(ValueError):
    """El contrato no se puede leer; el mensaje dice el campo, nunca su valor."""


@dataclass(frozen=True)
class Contrato:
    site: SiteParams
    precios: PrecioContrato
    periodo: Periodo
    total_factura: Decimal | None = None  # solo si el contrato salió de una factura subida


def _decimal(valor, campo: str) -> Decimal:
    if isinstance(valor, bool) or not isinstance(valor, (str, int)):
        raise ErrorContrato(f"{campo}: escribir el número como texto, por ejemplo \"0.15\"")
    try:
        d = Decimal(str(valor))
    except InvalidOperation:
        raise ErrorContrato(f"{campo}: no es un número") from None
    if not d.is_finite() or d < 0 or d > MAXIMO:
        raise ErrorContrato(f"{campo}: debe ser un número finito, no negativo y razonable")
    return d


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
        if type(inicio) is not date or type(fin) is not date:
            raise ErrorContrato("periodo: las fechas deben ser AAAA-MM-DD")
        if not 0 <= (fin - inicio).days < DIAS_MAXIMOS:
            raise ErrorContrato("periodo: el inicio debe ser anterior o igual al fin y el periodo, de menos de un año")
        tarifa = str(crudo["tarifa"])
        if tarifa == "otra" or tarifa not in PERIODOS_ENERGIA:
            raise ErrorContrato(f"tarifa: debe ser una de {', '.join(t for t in PERIODOS_ENERGIA if t != 'otra')}")
        potencia = _por_periodo(crudo["potencia_contratada_kw"], "potencia_contratada_kw")
        energia = _por_periodo(precios["energia_eur_kwh"], "precios.energia_eur_kwh")
        precio_potencia = _por_periodo(precios["potencia_eur_kw_anio"], "precios.potencia_eur_kw_anio")
        if not set(potencia) | set(precio_potencia) <= set(PERIODOS_POTENCIA[tarifa]) \
                or not set(energia) <= set(PERIODOS_ENERGIA[tarifa]):
            raise ErrorContrato("los periodos de potencia o energía no corresponden a la tarifa")
        site = SiteParams(tarifa, potencia,
                          ie_uso=str(crudo.get("ie_uso", "profesional")),
                          aplica_bono_social=bool(crudo.get("aplica_bono_social", False)),
                          alquiler_importe=(_decimal(crudo["alquiler_importe"], "alquiler_importe")
                                            if "alquiler_importe" in crudo else None))
        total = _decimal(crudo["total_factura"], "total_factura") if "total_factura" in crudo else None
        return Contrato(site, PrecioContrato(energia, precio_potencia), Periodo(inicio, fin), total)
    except KeyError as e:
        raise ErrorContrato(f"falta el campo {e.args[0]}") from None
    except TypeError:
        raise ErrorContrato("el contrato tiene una estructura inesperada") from None
