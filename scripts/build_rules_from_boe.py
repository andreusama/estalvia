#!/usr/bin/env python3
"""Genera los YAML de `rules/` a partir de las tablas del XML oficial del BOE.

Uso: python scripts/build_rules_from_boe.py [directorio_salida]
Requiere red. Los valores se copian de las tablas, nunca se teclean a mano; los impuestos
y los textos de calendario sí son manuales (ver rules/impuestos.yaml y rules/calendar/).
"""
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

TARIFAS = {"3.0TD": "3.0 TD", "6.1TD": "6.1 TD"}
SEGMENTO = {"3.0TD": "2", "6.1TD": "3"}  # RD 148/2021 art. 3.2: 1=2.0TD 2=3.0TD 3=6.1TD ...
PER = ["P1", "P2", "P3", "P4", "P5", "P6"]


def boe(id_):
    url = f"https://www.boe.es/diario_boe/xml.php?id={id_}"
    return ET.fromstring(urllib.request.urlopen(url, timeout=60).read())


def tables(root):
    out = []
    for tb in root.iter("table"):
        rows = []
        for tr in tb.iter("tr"):
            rows.append([re.sub(r"\s+", " ", "".join(c.itertext())).strip() for c in tr])
        out.append(rows)
    return out


def num(s):
    s = s.strip()
    return None if s in ("", "–", "-") else s.replace(".", "").replace(",", ".") if "," in s else s


def find(tbs, head):
    return next(t for t in tbs if head in t[0][-1] or head in t[0][0])


def rule(id_, kind, tariff, period, value, unit, desde, hasta, source):
    r = {"id": id_, "kind": kind, "tariff": tariff, "period": period, "value": value,
         "unit": unit, "valid_from": desde, "source": source}
    if hasta:
        r["valid_to"] = hasta
    return r


def tabla_total(tbs, titulo):
    t = next(t for t in tbs if titulo in t[0][-1])
    return {row[0]: row[1:] for row in t[2:]}


def peajes(year, id_, desde, hasta, src):
    tbs = tables(boe(id_))
    rules = []
    pot = tabla_total(tbs, "Término de potencia del peaje de transporte y distribución")
    ene = tabla_total(tbs, "Término de energía del peaje de transporte y distribución")
    for tar, lab in TARIFAS.items():
        for i, p in enumerate(PER):
            v = num(pot[lab][i])
            rules.append(rule(f"PEAJE-POT-{tar}-{p}-{year}", "peaje_potencia_eur_kw_anio", tar, p, v,
                              "EUR/kW/año", desde, hasta, src))
            v = num(ene[lab][i])
            rules.append(rule(f"PEAJE-ENE-{tar}-{p}-{year}", "peaje_energia_eur_kwh", tar, p, v,
                              "EUR/kWh", desde, hasta, src))
    return tbs, rules


def cargos(year, id_, desde, hasta, src):
    tbs = tables(boe(id_))
    rules = []
    for kind, head, unit, pre in [
        ("cargo_potencia_eur_kw_anio", "Término de potencia de los cargos", "EUR/kW/año", "CARGO-POT"),
        ("cargo_energia_eur_kwh", "Término de energía de los cargos", "EUR/kWh", "CARGO-ENE"),
        ("pago_capacidad_eur_kwh", "Término de energía de los pagos por capacidad", "EUR/kWh", "CAPAC"),
    ]:
        t = next(t for t in tbs if head in t[0][-1])
        by = {row[0]: row[1:] for row in t[2:]}
        for tar in TARIFAS:
            for i, p in enumerate(PER):
                v = num(by[SEGMENTO[tar]][i])
                if v is not None:
                    rules.append(rule(f"{pre}-{tar}-{p}-{year}", kind, tar, p, v, unit, desde, hasta,
                                      f"{src} (segmento tarifario {SEGMENTO[tar]} = {tar}, RD 148/2021 art. 3.2)"))
    return rules


def excesos_reactiva_2026(tbs, desde, src):
    rules = []
    for idx, (kind, unit, pre) in enumerate([
        ("exceso_potencia_tepp45_eur_kw_dia", "EUR/kW/día", "EXC45"),
        ("exceso_potencia_tepp123_eur_kw", "EUR/kW", "EXC123")]):
        t = [t for t in tbs if t[0][0] == "Periodo" and "3.0 TD" in t[0]][idx]
        col = {h: j for j, h in enumerate(t[0])}
        for row in t[1:]:
            p = "P" + row[0].split()[1].rstrip(".")
            for tar, lab in TARIFAS.items():
                v = num(row[col[lab]])
                if v is not None:
                    rules.append(rule(f"{pre}-{tar}-{p}-2026", kind, tar, p, v, unit, desde, None,
                                      f"{src}, Anexo II"))
    for id_, kind, val in [("REACT-080-095-2026", "reactiva_inductiva_cosphi_080_095_eur_kvarh", "0.0415540"),
                           ("REACT-LT080-2026", "reactiva_inductiva_cosphi_lt_080_eur_kvarh", "0.0623320")]:
        rules.append(rule(id_, kind, None, None, val, "EUR/kVArh",
                          desde, None, f"{src}, Anexo III (periodos 1 a 5; sin recargo si cos φ >= 0,95; "
                                       "periodo 6 capacitiva: 0 para cos φ < 0,98)"))
    return rules


MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre",
         "Octubre", "Noviembre", "Diciembre"]


def festivos(year, id_):
    """Festivos nacionales a efectos de periodos (Circular 3/2020 art. 7.2.b) y festivos de Cataluña."""
    t = tables(boe(id_))[0]
    mes = 0
    nac, cat = [], []
    for row in t[2:]:
        if row[0] in MESES:
            mes = MESES.index(row[0]) + 1
            continue
        m = re.match(r"(\d+) (.*)", row[0])
        if not m or len(row) < 20:
            continue
        fecha = f"{year}-{mes:02d}-{int(m.group(1)):02d}"
        nombre = m.group(2).rstrip(".")
        marcas = row[1:]
        # Nacional = marcado con un asterisco en todas las comunidades, con fecha fija
        # (Viernes Santo es nacional pero sin fecha fija, queda excluido por el art. 7.2.b).
        if all(x == "*" for x in marcas) and "Viernes Santo" not in nombre:
            nac.append({"fecha": fecha, "nombre": nombre})
        if marcas[8]:
            cat.append({"fecha": fecha, "nombre": nombre, "marca": marcas[8]})
    if not any(f["fecha"].endswith("-01-06") for f in nac):
        nac.append({"fecha": f"{year}-01-06", "nombre": "Epifanía del Señor (tipo D por el art. 7.2.b)"})
    return sorted(nac, key=lambda f: f["fecha"]), cat


def dump_festivos(out):
    doc = {
        "nacionales_tarifarios": {},
        "cataluna_informativo": {},
        "nota": "Los periodos tarifarios solo usan festivos NACIONALES (Circular 3/2020, art. 7.2.b); "
                "los festivos de Cataluña NO cambian los periodos. Marca * = nacional no sustituible, "
                "** = sustituible, *** = propio de la comunidad. Los locales no están incluidos.",
        "fuentes": {2025: "BOE-A-2024-21316", 2026: "BOE-A-2025-21667"},
    }
    for y, id_ in [(2025, "BOE-A-2024-21316"), (2026, "BOE-A-2025-21667")]:
        nac, cat = festivos(y, id_)
        doc["nacionales_tarifarios"][y] = nac
        doc["cataluna_informativo"][y] = cat
    d = out / "calendar"
    d.mkdir(exist_ok=True)
    (d / "festivos.yaml").write_text(
        "# Generado por scripts/build_rules_from_boe.py. No editar a mano.\n"
        + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("escrito", d / "festivos.yaml")


def dump(path, header, rules, verificar):
    doc = {"rules": rules, "verificar": verificar}
    path.write_text(header + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=140),
                    encoding="utf-8")
    print("escrito", path, len(rules), "reglas")


def main(out):
    out = Path(out)
    dump_festivos(out)
    out.mkdir(exist_ok=True)
    hdr = "# Generado por scripts/build_rules_from_boe.py desde el XML oficial del BOE. No editar a mano.\n"
    s25 = "Resolución CNMC 4/12/2024, BOE-A-2024-26218 (peajes T&D 2025)"
    s26 = "Resolución CNMC 18/12/2025, BOE-A-2025-26348 (peajes T&D 2026)"
    c25 = "Orden TED/1487/2024, BOE-A-2024-27289 (cargos 2025)"
    c26 = "Orden TED/1524/2025, BOE-A-2025-26705 (cargos 2026)"
    _, r = peajes(2025, "BOE-A-2024-26218", "2025-01-01", "2025-12-31", s25)
    dump(out / "peajes_2025.yaml", hdr, r, [
        "Excesos de potencia 2025 no cargados: el Anexo II fue modificado por Resolución 6/3/2025 (BOE-A-2025-5341).",
        "La corrección de errores de 23/12/2024 (BOE-A-2024-27271) solo afecta a tablas de autoconsumo (no usadas)."])
    tbs, r = peajes(2026, "BOE-A-2025-26348", "2026-01-01", None, s26)
    r += excesos_reactiva_2026(tbs, "2026-01-01", s26)
    dump(out / "peajes_2026.yaml", hdr, r, [
        "Sin valid_to: cerrar cuando se publique la resolución de peajes 2027.",
        "Comprobar que el Anexo II 2026 no tiene modificaciones posteriores."])
    dump(out / "cargos_2025.yaml", hdr, cargos(2025, "BOE-A-2024-27289", "2025-01-01", "2025-12-31", c25), [])
    dump(out / "cargos_2026.yaml", hdr, cargos(2026, "BOE-A-2025-26705", "2026-01-01", None, c26),
         ["Sin valid_to: cerrar cuando se publique la orden de cargos 2027."])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "rules")
