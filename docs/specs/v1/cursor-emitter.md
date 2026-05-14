# Cursor emitter v1

Status: Current
Date: 2026-05-14

## User-Global Output

The user-global Cursor emitter writes one rule file per resolved skill under:

- `~/.cursor/rules/<slug>.mdc`

Each emitted rule is symlinked through the team-agents library to a rendered file.

## Frontmatter

The emitted `.mdc` frontmatter includes:

- `description`
- `globs` only when declared by the source
- `alwaysApply` only when declared by the source

## Minimum Cursor Version

User-global `.cursor/rules/` support is required for the default v1 Cursor emitter path.

If a local Cursor install does not support user-global rules, workspace-local `.cursor/rules/` output from `team-agents sync` remains the fallback surface.
