"""RuleSet versionado: precios y porcentajes con vigencia y fuente normativa (TDD sección 7)."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, field_validator, model_validator

from .errors import MissingRuleError, RuleSetError


class Rule(BaseModel, frozen=True):
    id: str
    kind: str  # p. ej. potencia_eur_kw_anio, energia_eur_kwh, ie_pct, ie_min_eur_mwh, iva_pct
    tariff: Optional[str] = None
    period: Optional[str] = None
    value: Decimal
    unit: str
    valid_from: date
    valid_to: Optional[date] = None  # inclusive; None = sin fin
    source: str  # referencia normativa (BOE, CNMC...)

    @field_validator("value", mode="before")
    @classmethod
    def _no_float(cls, v):
        if isinstance(v, float):
            raise ValueError("usar cadena o entero para valores, no float")
        return v

    @model_validator(mode="after")
    def _check(self):
        if not self.source.strip():
            raise ValueError(f"regla {self.id}: sin fuente normativa")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError(f"regla {self.id}: vigencia invertida")
        return self

    def covers(self, d: date) -> bool:
        return self.valid_from <= d and (self.valid_to is None or d <= self.valid_to)


class RuleSet:
    def __init__(self, rules: list[Rule]):
        self.rules = tuple(rules)
        self._validate()

    def _validate(self) -> None:
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise RuleSetError("ids de regla duplicados")
        groups: dict[tuple, list[Rule]] = {}
        for r in self.rules:
            groups.setdefault((r.kind, r.tariff, r.period), []).append(r)
        for key, rs in groups.items():
            rs = sorted(rs, key=lambda r: r.valid_from)
            for a, b in zip(rs, rs[1:]):
                if a.valid_to is None or a.valid_to >= b.valid_from:
                    raise RuleSetError(f"vigencias solapadas en {key}: {a.id} y {b.id}")

    @property
    def hash(self) -> str:
        data = [r.model_dump(mode="json") for r in sorted(self.rules, key=lambda r: r.id)]
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def find(self, kind: str, d: date, tariff: str | None = None, period: str | None = None) -> Rule:
        for r in self.rules:
            if r.kind == kind and r.tariff == tariff and r.period == period and r.covers(d):
                return r
        raise MissingRuleError(
            f"sin regla vigente: kind={kind} tariff={tariff} period={period} fecha={d}"
        )

    def gaps(self) -> list[str]:
        """Huecos entre vigencias consecutivas (informativo; un hueco no es error por sí solo)."""
        out = []
        groups: dict[tuple, list[Rule]] = {}
        for r in self.rules:
            groups.setdefault((r.kind, r.tariff, r.period), []).append(r)
        for key, rs in groups.items():
            rs = sorted(rs, key=lambda r: r.valid_from)
            for a, b in zip(rs, rs[1:]):
                if a.valid_to is not None and (b.valid_from - a.valid_to).days > 1:
                    out.append(f"{key}: hueco entre {a.valid_to} y {b.valid_from}")
        return out

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RuleSet":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        try:
            return cls([Rule(**r) for r in raw.get("rules", [])])
        except ValueError as e:  # pydantic ValidationError hereda de ValueError
            raise RuleSetError(str(e)) from e
