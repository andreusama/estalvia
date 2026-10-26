"""Esquema de extracción y validaciones deterministas (TDD sección 6.1)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ValidationError, model_validator

TOLERANCIA_SUMA = Decimal("0.02")  # euros
PERIODOS = ("P1", "P2", "P3", "P4", "P5", "P6")
# Periodos tarifarios válidos por tarifa de acceso. `otra` no restringe: la tarifa no se conoce.
PERIODOS_ENERGIA = {"2.0TD": PERIODOS[:3], "3.0TD": PERIODOS, "6.1TD": PERIODOS, "otra": PERIODOS}
PERIODOS_POTENCIA = {"2.0TD": PERIODOS[:2], "3.0TD": PERIODOS, "6.1TD": PERIODOS, "otra": PERIODOS}


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


class LecturaContador(BaseModel):
    """Lectura acumulada del contador que imprime la factura en un periodo tarifario."""
    inicial: Decimal
    final: Decimal

    @model_validator(mode="after")
    def _orden(self):
        if self.final < self.inicial:
            raise ValueError("lectura del contador con final menor que la inicial")
        return self


class ConceptoRegulado(BaseModel):
    """Línea del desglose de costes regulados (peajes, cargos...) tal como la imprime la factura."""
    nombre: str
    importe: Decimal


class Impuestos(BaseModel):
    electrico: Decimal
    iva: Decimal


class FacturaExtraida(BaseModel):
    comercializadora: str
    cups: str
    tarifa_acceso: Literal["3.0TD", "6.1TD", "2.0TD", "otra"]
    modalidad_precio: Literal["fijo", "indexado", "pvpc", "desconocida"]
    periodo_facturado: PeriodoFacturado
    potencia_contratada_kw: dict[str, Decimal] = {}  # vacío = la factura no lo trae; validar_factura lo señala
    potencia_maxima_kw: dict[str, Decimal] = {}
    energia_kwh: dict[str, Decimal] = {}
    energia_reactiva_kvarh: dict[str, Decimal] = {}
    # Opcionales: None = la factura no lo imprime. Nunca se rellenan por defecto.
    lecturas_contador: dict[str, LecturaContador] | None = None
    desglose_regulado: list[ConceptoRegulado] | None = None
    conceptos: list[Concepto]
    impuestos: Impuestos
    total: Decimal
    confianza_campos: dict[str, float] = {}

    @model_validator(mode="after")
    def _periodos_validos(self):
        potencia, energia = PERIODOS_POTENCIA[self.tarifa_acceso], PERIODOS_ENERGIA[self.tarifa_acceso]
        campos = {"potencia_contratada_kw": potencia, "potencia_maxima_kw": potencia, "energia_kwh": energia,
                  "energia_reactiva_kvarh": energia, "lecturas_contador": energia}
        for campo, validos in campos.items():
            malas = set(getattr(self, campo) or ()) - set(validos)
            if malas:
                raise ValueError(f"{campo}: periodos no válidos para {self.tarifa_acceso}: {sorted(malas)}")
        return self


def validar_datos(datos: dict, otras: list[FacturaExtraida] | None = None) -> tuple[FacturaExtraida | None, list[str]]:
    """Punto de entrada para datos sin validar (salida de la IA): un fallo de esquema (campo crítico ausente,
    periodo no válido para la tarifa...) es un problema que lleva a Revisión, no una excepción. Los mensajes
    nombran el campo y la regla, nunca el valor recibido (puede ser un dato personal)."""
    try:
        f = FacturaExtraida.model_validate(datos)
    except ValidationError as e:
        return None, [f"{'.'.join(str(x) for x in err['loc']) or 'factura'}: {err['msg']}" for err in e.errors()]
    return f, validar_factura(f, otras)


def validar_factura(f: FacturaExtraida, otras: list[FacturaExtraida] | None = None) -> list[str]:
    """Devuelve la lista de problemas; vacía = pasa. Si hay alguno, la factura va a Revisión."""
    problemas: list[str] = []
    for campo in ("potencia_contratada_kw", "energia_kwh", "conceptos"):
        if not getattr(f, campo):
            problemas.append(f"falta {campo}: no se puede recalcular sin ese campo")
    suma = sum((c.importe for c in f.conceptos), Decimal(0)) + f.impuestos.electrico + f.impuestos.iva
    if abs(suma - f.total) > TOLERANCIA_SUMA:
        problemas.append(f"la suma de conceptos e impuestos ({suma}) no cuadra con el total ({f.total}) "
                         f"por más de {TOLERANCIA_SUMA}")
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
