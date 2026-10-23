---
name: es-electricity-tariffs
description: Usar al tocar tarifas (3.0TD, 6.1TD), periodos horarios, reglas, peajes, cargos o impuestos del código o de `rules/`.
---
# Tarifas eléctricas y RuleSet
1. Nunca escribas precios, porcentajes ni periodos en el código. Van en `rules/*.yaml`.
2. Cada regla: `id, kind, tariff, period, value (cadena), unit, valid_from, valid_to, source`.
   Sin `source` el RuleSet no se publica. Kinds en uso: `peaje_potencia_eur_kw_anio`, `peaje_energia_eur_kwh`, `cargo_potencia_eur_kw_anio`,
   `cargo_energia_eur_kwh`, `pago_capacidad_eur_kwh`, `exceso_potencia_tepp45_eur_kw_dia`, `exceso_potencia_tepp123_eur_kw`,
   `reactiva_inductiva_*`, `ie_pct`, `ie_min_eur_mwh` (period=profesional|otros), `iva_pct`; el motor también espera
   `potencia_eur_kw_anio` y `energia_eur_kwh` del contrato.
3. Si no tienes el dato oficial (BOE/CNMC), no lo inventes: deja el campo vacío, marca `VERIFICAR` y pídelo.
4. Tras editar, ejecuta `python scripts/validate_rules.py rules` (falla por fuente ausente o vigencias solapadas;
   avisa de huecos).
5. Un RuleSet publicado es inmutable: añade reglas nuevas con nueva vigencia, no edites las antiguas.
6. Los datos regulatorios que añadas a `references/` llevan fuente y fecha de consulta.

Glosario: potencia contratada, peajes (acceso), cargos, término de potencia/energía, excesos de potencia,
energía reactiva (cos φ), IE (impuesto sobre la electricidad). Ver TDD secciones 7 y 13.
Estado: IVA/IE temporales de 2026 sin confirmar → VERIFICAR contra BOE/CNMC.

Carga de datos: `python scripts/build_rules_from_boe.py` regenera `rules/` desde el XML del BOE. Cada año nuevo: añadir ids de resolución/orden en el script,
cerrar con `valid_to` las reglas del año anterior y ejecutar los tests de `tests/test_real_rules.py`.
Cataluña: mismas reglas; solo festivos nacionales cuentan para periodos. Ver `rules/README.md`.
