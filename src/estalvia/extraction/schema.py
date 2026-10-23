"""Esquema de extracción y validaciones deterministas (TDD sección 6.1)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, model_validator

TOLERANCIA_SUMA = Decimal("0.02")  # euros
PERIODOS = ("P1", "P2", "P3", "P4", "P5", "P6")


class Concepto(BaseModel):
    nombre: str
    cantidad: Decimal
    precio: Decimal
    importe: Decimal


class PeriodoFacturado(BaseModel):
    inicio: date
    fin: date

    @model_validator(mode="after")
    def _orden(self):
        if self.fin < self.inicio:
            raise ValueError("periodo facturado con fin anterior al inicio")
        return self


class Impuestos(BaseModel):
    electrico: Decimal
    iva: Decimal


class FacturaExtraida(BaseModel):
    comercializadora: str
    cups: str
    tarifa_acceso: Literal["3.0TD", "6.1TD", "otra"]
    modalidad_precio: Literal["fijo", "indexado", "pvpc", "desconocida"]
    periodo_facturado: PeriodoFacturado
    potencia_contratada_kw: dict[str, Decimal]
    potencia_maxima_kw: dict[str, Decimal] = {}
    energia_kwh: dict[str, Decimal] = {}
    energia_reactiva_kvarh: dict[str, Decimal] = {}
    conceptos: list[Concepto]
    impuestos: Impuestos
    total: Decimal
    confianza_campos: dict[str, float] = {}

    @model_validator(mode="after")
    def _claves(self):
        for campo in ("potencia_contratada_kw", "potencia_maxima_kw", "energia_kwh",
                      "energia_reactiva_kvarh"):
            malas = set(getattr(self, campo)) - set(PERIODOS)
            if malas:
                raise ValueError(f"{campo}: periodos desconocidos {sorted(malas)}")
        return self


def validar_factura(f: FacturaExtraida, otras: list[FacturaExtraida] | None = None) -> list[str]:
    """Devuelve la lista de problemas; vacía = pasa. Si hay alguno, la factura va a `a_revisar`."""
    problemas: list[str] = []
    suma = sum((c.importe for c in f.conceptos), Decimal(0)) + f.impuestos.electrico + f.impuestos.iva
    if abs(suma - f.total) > TOLERANCIA_SUMA:
        problemas.append(f"la suma de conceptos e impuestos ({suma}) no cuadra con el total ({f.total})")
    for o in otras or []:
        if o.cups == f.cups and not (
            f.periodo_facturado.fin < o.periodo_facturado.inicio
            or o.periodo_facturado.fin < f.periodo_facturado.inicio
        ):
            problemas.append("el periodo se solapa con otra factura del mismo suministro")
    if any(v < 0 for v in f.energia_kwh.values()):
        problemas.append("kWh negativos")
    # Rangos plausibles por tarifa y lista de conceptos conocidos: VERIFICAR, requieren datos reales.
    return problemas
