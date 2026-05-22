# item.toml v1

Status: Frozen
Date: 2026-05-14

## Purpose

This document freezes the `item.toml` contract for team-agents v1 items.

It applies to every item kind:

- `skill`
- `policy`
- `context`

The canonical machine-readable schema lives at [src/team_agents/schemas/item-toml-v1.schema.json](/home/jay/dev/Tools/corporate_standardized_agents/src/team_agents/schemas/item-toml-v1.schema.json:1).

## Required Fields

| Field | Type | Rules |
| --- | --- | --- |
| `id` | string | Must match canonical id format: `<source-type>.<namespace>.<kind>.<slug>` |
| `kind` | string | Must be one of `skill`, `policy`, `context` |
| `title` | string | Non-empty human-readable title |
| `privacy` | string | Must be `corp-private` or `repo-safe` |

## Optional Fields

| Field | Type | Rules |
| --- | --- | --- |
| `tags` | array of string | Free-form classification tags |
| `recommended_agent_types` | array of string | Agent types that are a good fit for this item |
| `timeout_seconds` | integer | Positive integer timeout hint |
| `source_note` | string | Human-readable provenance note |
| `source_ref` | string | Explicit source reference override |
| `target_tools` | array of string | Optional runtime restriction; each value must be `claude`, `codex`, or `cursor` |
| `claude_model` | string | Optional Claude-specific model hint |
| `cursor_globs` | array of string | Optional Cursor rule glob targeting |
| `cursor_always_apply` | boolean | Optional Cursor always-apply flag |
| `policy_rules` | array of object | Optional structured policy rules for `kind = "policy"` items |
| `usage_mode` | string | Optional lifecycle hint; must be `reusable` or `one-time` |

## Invariants

- Unknown top-level fields are invalid.
- The `kind` field must agree with the canonical id kind segment.
- `timeout_seconds` must be greater than or equal to `1`.
- `item.toml` declares metadata only. Human-readable body content remains in `body.md`.
- `usage_mode = "one-time"` marks an item as eligible for local completion suppression; it does not imply automatic mutation by the resolver.

## Notes

- This contract defines one item shape that can carry baseline metadata plus reserved tool-specific metadata.
- The current repo has fixture `item.toml` files under `examples/` and no native `item.toml` fixtures under `.agents/`; contract tests validate both locations.
