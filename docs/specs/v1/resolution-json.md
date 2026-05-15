# resolution.json v1

Status: Frozen
Date: 2026-05-14

## Purpose

This document freezes the `resolution.json` output contract for team-agents v1.

`resolution.json` is the machine-readable summary written under `.agents/` and consumed by:

- agent runtimes
- `team-agents audit`
- `team-agents doctor`
- any downstream tooling that needs to inspect resolved provenance

The canonical machine-readable schema lives at [src/team_agents/schemas/resolution-json-v1.schema.json](/home/jay/dev/Tools/corporate_standardized_agents/src/team_agents/schemas/resolution-json-v1.schema.json:1).

## Top-Level Contract

Required top-level fields:

- `schema_version`
- `workspace`
- `git_root`
- `normalized_remotes`
- `matched_repo_id`
- `matched_repo_group_id`
- `binding_name`
- `repo_class`
- `layer_chain`
- `applied_layers`
- `enabled_sources`
- `source_details`
- `enabled_skills`
- `active_policies`
- `active_docs`
- `recommended_agent_types`
- `warnings`
- `items`
- `denied_items`

## Provenance Guarantees

- Every resolved or denied item records its `layer_name`, `status`, `activated_by`, `source_type`, `source_namespace`, and `source_ref`.
- Items may optionally record `usage_mode` when the source metadata marks them as `one-time`.
- Replacements additionally record `replaced_from`.
- Field overrides are tracked through `status = "field-overridden"` plus `overridden_by`.
- Source trust metadata is frozen under `source_details`.
- The layer model is explicit through:
  - `layer_chain`: the canonical resolution order
  - `applied_layers`: the actual layers used for this resolution

## Privacy Rule

- Client repos must not inline `body` for corp-private items.
- Denied items never inline `body`.

## Notes

- `schema_version = "v1"` is part of the frozen contract.
- Human sign-off on this frozen contract is still required in the issue tracker.
