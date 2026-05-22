# Item Schema v1

Items are canonical, Git-backed standards units. Each item lives in a folder with `item.toml` and `body.md`.

Required fields:

- `id`: canonical id, `corp|external|user.<namespace>.<kind>.<slug>`
- `kind`: `skill`, `policy`, `context`, `completion_gate`, `playbook`, `pack`, or `profile`
- `title`: human-readable title
- `privacy`: `repo-safe` or `corp-private`

Optional fields include tags, recommended agent types, timeout, source note, target-tool settings, policy/completion_gate rules, usage mode, ownership metadata, lifecycle metadata, review/trust metadata, and skill `promotion_checklist` metadata.

Ownership and lifecycle metadata:

- `owner`: owning team, group, or accountable person
- `maintainer`: current maintainer or rotation responsible for updates
- `status`: `draft`, `active`, `deprecated`, or `archived`
- `review_status`: `unreviewed`, `reviewed`, or `approved`
- `deprecated_by`: replacement item id or migration target, when deprecated
- `sunset_after`: date or timestamp after which the item should no longer be selected

Generated context exposes item `status` as `lifecycle_status` so it does not conflict with resolution status (`direct`, `replaced`, or `field-overridden`). `team-agents audit` and `doctor` surface active deprecated items; audit also reports missing ownership metadata as sprawl warnings.

Review/trust metadata:

- `trust_level`: `unreviewed`, `user-trusted`, `corp-reviewed`, or `corp-required`
- `allows_scripts`: must be `false` in v1; executable scripts/resources are out of scope
- `reviewed_by`: reviewer identity, when reviewed
- `reviewed_at`: review date or timestamp, when reviewed

External skills and imported user skills default to `unreviewed`. Local user-authored items default to `user-trusted`. Corp-authored items default to `corp-reviewed` unless explicitly marked otherwise.

Compatibility metadata:

- `applies_to_languages`: language tags such as `python` or `typescript`
- `applies_to_frameworks`: framework tags such as `django` or `react`
- `compatible_versions`: framework version constraints such as `{ django = ">=4.2,<6" }`
- `repo_tags`: repo or architecture tags such as `web-api`

Resolvers warn on likely mismatches when the active repo/profile context declares languages, frameworks, framework versions, or repo tags. Compatibility warnings do not block activation in v1.

Completion Gate and playbook items may define `evidence_required` to make completion proof explicit:

```toml
evidence_required = [
  "tests_run",
  "files_changed_summary",
  "risk_notes",
  "verification_command_output"
]
```

Playbook items may also define structured, non-executable boundaries:

```toml
inputs = ["issue", "repo_context"]
outputs = ["patch", "verification_report"]
stop_conditions = ["ambiguous_requirement", "security_boundary_unclear"]
```

Generated context and audit output surface active completion gate and playbook evidence requirements. Active playbooks also render their declared inputs, outputs, evidence requirements, and stop conditions. v1 does not automatically execute playbooks or enforce evidence submission.

Skill items may define `[promotion_checklist]` before they are promoted into corp or repo baselines:

- `task`: the task the skill improves
- `applicability`: repo, language, framework, or version boundaries
- `evidence`: measured or observed evidence that it helps
- `risks`: ways the skill can hurt or mislead work
- `scope`: why the skill is not too broad
- `redundancy`: why existing contexts/completion gates do not already cover it

Pack items may also define `[activation] required` and `[activation] enabled` to bundle other standards. Pack `required` entries may reference policies, completion gates, and packs. Pack `enabled` entries may reference skills, policies, contexts, completion gates, playbooks, and packs. The machine-readable schema is `schemas/item.schema.json`.
