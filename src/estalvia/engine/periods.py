"""Periodo tarifario (P1-P6) de una hora en la Península para 3.0TD y 6.xTD.

Datos en rules/calendar/. Cataluña usa la misma tabla: solo cuentan los festivos NACIONALES
(Circular 3/2020, art. 7.2.b). Sin acceso a disco aquí: el llamante carga los YAML.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from .errors import MissingDataError


class Calendario:
    def __init__(self, periodos: dict, festivos: dict):
        self._temporada = {m: t for t, ms in periodos["temporadas"].items() for m in ms}
        self._horas = periodos["horas"]
        self._festivos = {
            date.fromisoformat(f["fecha"]) for ys in festivos["nacionales_tarifarios"].values() for f in ys
        }
        self._anios = {int(y) for y in festivos["nacionales_tarifarios"]}

    @classmethod
    def desde_directorio(cls, d: str | Path) -> Calendario:
        d = Path(d)
        load = lambda n: yaml.safe_load((d / n).read_text(encoding="utf-8"))  # noqa: E731
        return cls(load("periodos_horarios.yaml"), load("festivos.yaml"))

    def tipo_dia(self, d: date) -> str:
        if d.year not in self._anios:
            raise MissingDataError(f"sin calendario de festivos para {d.year}")
        if d.weekday() >= 5 or d in self._festivos:
            return "D"
        return {"alta": "A", "media_alta": "B", "media": "B1", "baja": "C"}[self._temporada[d.month]]

    def periodo(self, d: date, hora: int) -> str:
        """`hora` = hora local de inicio (0-23). En días de 23/25 horas el llamante resuelve la hora local."""
        for p, tramos in self._horas[self.tipo_dia(d)].items():
            if any(a <= hora < b for a, b in tramos):
                return p
        raise MissingDataError(f"hora sin periodo: {d} {hora}")
