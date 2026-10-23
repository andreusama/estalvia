#!/usr/bin/env python3
"""Valida los RuleSet YAML de un directorio: fuente obligatoria y vigencias sin solapes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from estalvia.engine.errors import RuleSetError
from estalvia.engine.rules import RuleSet


def main(d: str) -> int:
    rc = 0
    todas = []
    for f in sorted(Path(d).glob("*.yaml")):
        try:
            rs = RuleSet.from_yaml(f)
        except RuleSetError as e:
            print(f"FALLA {f}: {e}")
            rc = 1
            continue
        todas += rs.rules
        print(f"OK {f} ({len(rs.rules)} reglas, hash {rs.hash[:12]})")
        for g in rs.gaps():
            print(f"  aviso: {g}")
    if todas:  # todos los ficheros juntos: sin ids repetidos ni vigencias solapadas entre ficheros
        try:
            RuleSet(todas)
        except RuleSetError as e:
            print(f"FALLA conjunto: {e}")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "rules"))
