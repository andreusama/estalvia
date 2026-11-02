# Glossary Map

## Contexts

- [Copiloto energético](./GLOSSARY.md): lee facturas de luz y consumos horarios de una pyme y devuelve un informe de ahorro verificable.
- [Bar](./prototipos/bar/GLOSSARY.md): digitaliza albaranes y facturas de proveedores de un bar a partir de fotos y dice qué está pagado, qué está pendiente y qué no cuadra.

## Relationships

- **Copiloto energético ↔ Bar**: sin relación por ahora. Comparten la palabra "factura" con significados distintos (factura de luz frente a factura de proveedor): cada contexto usa solo la suya. Los prototipos nuevos viven en `prototipos/<nombre>/`.
- **Plataforma → Bar**: la plataforma (un solo proyecto de Vercel, ver [ADR 0001](./docs/adr/0001-una-plataforma-un-proyecto-vercel.md)) monta el Bar como app bajo `/bar/`. El copiloto energético sigue solo en local.
