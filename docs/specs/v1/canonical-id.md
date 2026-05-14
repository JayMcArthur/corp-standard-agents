# canonical id v1

Status: Frozen
Date: 2026-05-14

## Purpose

This document freezes the canonical id format used by every item in team-agents v1.

Canonical ids are the stable cross-layer reference for:

- item activation
- item override
- item replacement
- provenance in `resolution.json`

## Grammar

Canonical id format:

```text
<source-type>.<source-namespace>.<kind>.<slug>
```

Segments:

1. `source-type`
   - one of `corp`, `user`, `external`
2. `source-namespace`
   - lowercase ASCII
   - first character must be alphanumeric
   - remaining characters may be lowercase ASCII letters, digits, `_`, or `-`
3. `kind`
   - one of `skill`, `policy`, `doc`
4. `slug`
   - lowercase ASCII
   - first character must be alphanumeric
   - remaining characters may be lowercase ASCII letters, digits, `_`, or `-`

Regex:

```text
^(corp|external|user)\.([a-z0-9][a-z0-9_-]*)\.(skill|policy|doc)\.([a-z0-9][a-z0-9_-]*)$
```

## Reserved Prefixes

- `corp.` is reserved for corp-authored items
- `user.` is reserved for user-layer items
- `external.` is reserved for items originating from external sources

No other first segment is valid in v1.

## Collision Behavior

- Duplicate canonical ids within the same loaded layer are invalid and must fail validation.
- Duplicate canonical ids across different layers are allowed only through normal overlay semantics:
  - a later layer may replace an earlier item with the same id
  - item overrides apply by canonical id
- The canonical id is the disambiguation boundary. Two items with different ids are always distinct, even if titles or slugs match.

## Notes

- The `kind` segment and the item's declared `kind` field must agree.
- Human sign-off on this frozen contract is still required in the issue tracker.
