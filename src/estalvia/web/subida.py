"""Datos subidos desde la web (ticket #32): contrato a partir de la factura extraída y almacén local.

La IA lee la factura; aquí solo se buscan, por nombre y periodo, las líneas que la factura imprime con su precio.
Si falta alguna no se estima: el error dice cuál.
"""
from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from decimal import Decimal
from pathlib import Path

import yaml

from estalvia.analysis.nucleo import PrecioContrato
from estalvia.engine.calc import Periodo, SiteParams
from estalvia.extraction.schema import PERIODOS_ENERGIA, PERIODOS_POTENCIA, FacturaExtraida

from .contrato import Contrato, ErrorContrato

_PERIODO = re.compile(r"\bp([1-6])\b")


def _norma(nombre: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", nombre.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


# Nombres con que las facturas (castellano y catalán) rotulan cada línea. Una factura nueva puede traer otros:
# entonces falta el precio y el error lo dice, no se adivina.
NOMBRES_ENERGIA = ("energ",)
NOMBRES_POTENCIA = ("potencia", "terme fix", "termino fijo")
NOMBRES_BONO_SOCIAL = ("bono social", "bo social")
NOMBRES_ALQUILER = ("alquiler", "lloguer")


def _precios(f: FacturaExtraida, nombres: tuple[str, ...], excluir: tuple[str, ...]) -> dict[str, Decimal]:
    precios: dict[str, Decimal] = {}
    for c in f.conceptos:
        n = _norma(c.nombre)
        m = _PERIODO.search(n)
        if not any(x in n for x in nombres) or m is None or c.precio is None or any(x in n for x in excluir):
            continue
        periodo = f"P{m.group(1)}"
        if periodo in precios and precios[periodo] != c.precio:
            raise ErrorContrato(f"hay varios precios distintos para {n.strip()}")
        precios[periodo] = c.precio
    return precios


def contrato_desde_factura(f: FacturaExtraida) -> Contrato:
    tarifa = f.tarifa_acceso
    if tarifa == "otra":
        raise ErrorContrato("tarifa: no se reconoce la tarifa de acceso de la factura")
    energia = _precios(f, NOMBRES_ENERGIA, ("reactiv", "excedent", "compens"))
    por_dia = _precios(f, NOMBRES_POTENCIA, ("exceso", "maxim", "reactiv"))
    esperados = {"energía": [p for p in PERIODOS_ENERGIA[tarifa] if p in f.energia_kwh],
                 "potencia": [p for p in PERIODOS_POTENCIA[tarifa] if p in f.potencia_contratada_kw
                              and f.potencia_contratada_kw[p] > 0]}
    for p in esperados["energía"]:
        if p not in energia:
            raise ErrorContrato(f"falta el precio de energía {p} en las líneas de la factura")
    for p in esperados["potencia"]:
        if p not in por_dia:
            raise ErrorContrato(f"falta el precio de potencia {p} en las líneas de la factura")
    # VERIFICAR: se supone que la factura imprime la potencia en EUR/kW·día y que anual = día x días del año.
    # Lo vigila la comparación de la línea base con el total impreso (web/views.py).
    anio = f.periodo_facturado.inicio.year
    dias_anio = 366 if anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0) else 365
    potencia = {p: v for p, v in f.potencia_contratada_kw.items() if p in por_dia}
    nombres = [_norma(c.nombre) for c in f.conceptos]
    alquiler = sum((c.importe for c in f.conceptos if any(x in _norma(c.nombre) for x in NOMBRES_ALQUILER)), Decimal(0))
    site = SiteParams(tarifa, potencia, alquiler_importe=alquiler or None,
                      aplica_bono_social=any(x in n for n in nombres for x in NOMBRES_BONO_SOCIAL))
    return Contrato(site, PrecioContrato(energia, {p: por_dia[p] * dias_anio for p in potencia}),
                    Periodo(f.periodo_facturado.inicio, f.periodo_facturado.fin), f.total)


def contrato_a_yaml(c: Contrato) -> str:
    """El mismo formato que lee `cargar_contrato`: importes como texto, nunca como coma flotante."""
    datos = {
        "tarifa": c.site.tarifa,
        "potencia_contratada_kw": {p: str(v) for p, v in c.site.potencia_contratada_kw.items()},
        "precios": {"energia_eur_kwh": {p: str(v) for p, v in c.precios.energia_eur_kwh.items()},
                    "potencia_eur_kw_anio": {p: str(v) for p, v in c.precios.potencia_eur_kw_anio.items()}},
        "periodo": {"inicio": c.periodo.inicio, "fin": c.periodo.fin},
        "ie_uso": c.site.ie_uso, "aplica_bono_social": c.site.aplica_bono_social,
    }
    if c.total_factura is not None:
        datos["total_factura"] = str(c.total_factura)
    if c.site.alquiler_importe is not None:
        datos["alquiler_importe"] = str(c.site.alquiler_importe)
    return yaml.safe_dump(datos, sort_keys=False, allow_unicode=True)


def preparar_carpeta(carpeta: Path) -> None:
    """Carpeta privada (700) que no es un enlace simbólico."""
    if carpeta.is_symlink():
        raise OSError("la carpeta de subidas es un enlace simbólico; no se escribe a través de ella")
    carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
    carpeta.chmod(0o700)


def guardar_privado(carpeta: Path, nombre: str, datos: bytes) -> Path:
    """Escribe `carpeta/nombre` con permisos 600 en una carpeta 700, sin seguir enlaces simbólicos, y lo
    sustituye de golpe: nunca queda a medias. El nombre lo pone el código, jamás el cliente."""
    preparar_carpeta(carpeta)
    fd, temporal = tempfile.mkstemp(dir=carpeta, prefix=".", suffix=".tmp")  # mkstemp crea con permisos 600
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
        os.replace(temporal, carpeta / nombre)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)
    return carpeta / nombre
