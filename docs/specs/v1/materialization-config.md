# Materialization Config v1

Machine config stores materialization under `[materialization]`.

Supported strategies:

- `auto`
- `copy`
- `symlink`
- `junction`
- `hardlink`
- `render-only`

`auto` resolves to the platform-safe default. `render-only` avoids exposing source library paths in generated output while preserving rendered tool files. The machine-readable schema is `schemas/materialization.schema.json`.
