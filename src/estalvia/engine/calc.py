"""Motor de cálculo determinista. Sin Django, sin IA, sin acceso a datos (TDD sección 7).

Cubre: término de potencia, término de energía, impuesto sobre la electricidad, alquiler
de equipos e IVA. Excesos de potencia y energía reactiva NO están implementados: su fórmula
normativa está pendiente de VERIFICAR (ver DECISIONS.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from .errors import MissingDataError
from .rules import RuleSet

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fin: date  # inclusive

    def dias(self) -> list[date]:
        if self.fin < self.inicio:
            raise MissingDataError("periodo con fin anterior al inicio")
        n = (self.fin - self.inicio).days + 1
        return [self.inicio + timedelta(days=i) for i in range(n)]


@dataclass(frozen=True)
class SiteParams:
    tarifa: str
    potencia_contratada_kw: dict[str, Decimal]
    # Política de redondeo explícita; el de cada comercializadora es un parámetro.
    redondeo: str = ROUND_HALF_UP
    alquiler_eur_dia: Optional[Decimal] = None  # lo declara la factura
    # Uso de la electricidad para el mínimo del IE: "profesional" u "otros" (VERIFICAR con la factura).
    ie_uso: str = "profesional"


@dataclass(frozen=True)
class Lecturas:
    energia_kwh: dict[str, Decimal]  # kWh del periodo facturado por periodo tarifario


@dataclass(frozen=True)
class Linea:
    concepto: str
    base: Decimal
    precio: Decimal
    importe: Decimal
    regla_id: str
    vigencia: str
    fuente: str


@dataclass(frozen=True)
class Desglose:
    lineas: tuple[Linea, ...]
    total: Decimal
    ruleset_hash: str = ""


def _q(x: Decimal, mode: str) -> Decimal:
    return x.quantize(CENT, rounding=mode)


def _vig(r) -> str:
    return f"{r.valid_from}/{r.valid_to or ''}"


def _linea(concepto, base, precio, importe, r, mode) -> Linea:
    return Linea(concepto, base, precio, _q(importe, mode), r.id, _vig(r), r.source)


def calcular_factura(site: SiteParams, lecturas: Lecturas, reglas: RuleSet, periodo: Periodo) -> Desglose:
    mode = site.redondeo
    dias = periodo.dias()
    lineas: list[Linea] = []

    # Término de potencia: kW x precio anual / días del año, día a día (la regla puede cambiar
    # dentro del periodo y el año bisiesto se trata por fecha). Prorrateo: VERIFICAR.
    for p, kw in sorted(site.potencia_contratada_kw.items()):
        acum = Decimal(0)
        ultima = None
        for d in dias:
            r = reglas.find("potencia_eur_kw_anio", d, site.tarifa, p)
            dias_anio = 366 if (date(d.year, 12, 31) - date(d.year, 1, 1)).days == 365 else 365
            acum += kw * r.value / Decimal(dias_anio)
            ultima = r
        lineas.append(_linea(f"potencia {p}", kw, ultima.value, acum, ultima, mode))

    # Término de energía: una única regla por periodo tarifario; si cambia dentro del
    # periodo facturado hay que partir las lecturas (no se asume nada en silencio).
    for p, kwh in sorted(lecturas.energia_kwh.items()):
        r0 = reglas.find("energia_eur_kwh", periodo.inicio, site.tarifa, p)
        r1 = reglas.find("energia_eur_kwh", periodo.fin, site.tarifa, p)
        if r0.id != r1.id:
            raise MissingDataError(
                f"la regla de energía {p} cambia dentro del periodo; dividir las lecturas"
            )
        lineas.append(_linea(f"energia {p}", kwh, r0.value, kwh * r0.value, r0, mode))

    if site.alquiler_eur_dia is not None:
        n = Decimal(len(dias))
        lineas.append(
            Linea("alquiler equipos", n, site.alquiler_eur_dia,
                  _q(n * site.alquiler_eur_dia, mode), "factura", "", "declarado en factura")
        )

    base = sum((l.importe for l in lineas if l.concepto != "alquiler equipos"), Decimal(0))
    alquiler = sum((l.importe for l in lineas if l.concepto == "alquiler equipos"), Decimal(0))

    # Impuesto sobre la electricidad: porcentaje sobre la base con mínimo por MWh.
    f = periodo.fin
    ie_pct = reglas.find("ie_pct", f)
    ie_min = reglas.find("ie_min_eur_mwh", f, period=site.ie_uso)
    mwh = sum(lecturas.energia_kwh.values(), Decimal(0)) / Decimal(1000)
    ie = max(base * ie_pct.value / Decimal(100), mwh * ie_min.value)
    lineas.append(_linea("impuesto electricidad", base, ie_pct.value, ie, ie_pct, mode))

    iva = reglas.find("iva_pct", f)
    sin_iva = base + lineas[-1].importe + alquiler
    total = _q(sin_iva * (1 + iva.value / Decimal(100)), mode)
    lineas.append(_linea("iva", sin_iva, iva.value, total - sin_iva, iva, mode))
    return Desglose(tuple(lineas), total, reglas.hash)
