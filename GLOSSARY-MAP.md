# Glossary Map

## Contexts

- [Bar](./prototipos/bar/GLOSSARY.md): digitaliza albaranes y facturas de proveedores de un bar a partir de fotos y dice qué está pagado, qué está pendiente y qué no cuadra.
- [Birròmetro](./prototipos/birrometro/GLOSSARY.md): calcula cuánto se gana con un barril de cerveza según las raciones (zurritos, cañas, jarras) que se sacan.

## Relationships

- **Plataforma → Bar**: la plataforma (un solo proyecto de Vercel, ver [ADR 0001](./docs/adr/0001-una-plataforma-un-proyecto-vercel.md)) monta el Bar bajo `/bar/` y el Birròmetro bajo `/birrometro/`, cada uno como app independiente (no comparten modelos ni pantallas; ambos usan la misma cuenta de usuario). Los prototipos nuevos viven en `prototipos/<nombre>/` y se añaden aquí.
