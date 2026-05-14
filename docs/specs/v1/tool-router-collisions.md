# tool router collisions v1

Status: Frozen
Date: 2026-05-14

## Purpose

This document freezes collision behavior for the three router files team-agents may write into a workspace:

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules/team-agents.mdc`

These rules define when team-agents may create, merge, append, or refuse.

## Managed Block Markers

The managed block syntax is frozen:

```md
<!-- team-agents:start -->
... team-agents managed content ...
<!-- team-agents:end -->
```

If both markers are present, team-agents replaces only the content between them and preserves surrounding user text.

## Collision Rules

For each router target, team-agents applies the same write rules:

1. If the target file does not exist, team-agents may create it.
2. If the target file exists and already contains both managed markers, team-agents may replace only the managed region.
3. If the target file exists without a managed block:
   - in an `internal` repo, team-agents may append a managed block at the end of the file
   - in a `client` repo, team-agents must refuse
4. If generated `.agents/` content is tracked in git, team-agents must refuse before writing any router file.

## Diagnostics

Refusals must be explicit and user-visible.

Frozen diagnostic shapes:

- tracked generated content:
  - `Tracked .agents content already exists; refusing generated output`
- existing router without managed block in a client repo:
  - `Tracked <router-path> in a client repo cannot be updated`

## Notes

- The collision contract is path-sensitive; `.cursor/rules/team-agents.mdc` is treated as a first-class router target, not a generic doc file.
- Human sign-off on this frozen contract is still required in the issue tracker.
