# Authoring Guide

This guide describes the authoring model for `team-agents` standards repos and local user layers.

## Quick Start

Create starter scaffolds:

```bash
team-agents init-corp-repo --dest /path/to/corp-control
team-agents init-user-layer --dest ~/team-agents-user
team-agents setup --corp-repo /path/to/corp-control --user-path ~/team-agents-user
```

Corp-managed user profiles remain available when a company explicitly wants that audit model:

```bash
team-agents setup --corp-repo /path/to/corp-control --user alice
```

## Folder Shape

Corporate standards repo:

```text
corp-control/
  org/
    config.toml
    contexts/
    policies/
    completion_gates/
    skills/
    playbooks/
    packs/
    profiles/
    sources/
  repo-groups/
    <group-id>/
      config.toml
      contexts/
      policies/
      completion_gates/
      skills/
      playbooks/
      packs/
      profiles/
  repos/
    <repo-id>/
      config.toml
      contexts/
      policies/
      completion_gates/
      skills/
      playbooks/
      packs/
      profiles/
  indexes/
    repos.toml
    repo-groups.toml
    sources.toml
```

Local user layer:

```text
~/team-agents-user/
  config.toml
  contexts/
  policies/
  completion_gates/
  skills/
  playbooks/
  packs/
  profiles/
  activations/
  sources/
  workspaces/
```

## Item Kinds

Use the smallest fitting item kind:

- `context`: reference knowledge or context
- `policy`: rule or guidance
- `completion_gate`: required behavior, boundaries, definition of done, and evidence requirements
- `skill`: reusable agent capability
- `playbook`: repeatable playbook, not executable automation in v1
- `pack`: bundle of standards
- `profile` or `job`: lightweight work mode that selects context

## Canonical IDs

Every item id must match:

```text
<source-type>.<namespace>.<kind>.<slug>
```

Allowed values:

- `source-type`: `corp`, `external`, `user`
- `kind`: `skill`, `policy`, `context`, `completion_gate`, `playbook`, `pack`, `profile`
- `namespace`: lowercase ASCII, digits, `_`, `-`
- `slug`: lowercase ASCII, digits, `_`, `-`

Examples:

- `corp.shadowknight.completion_gate.definition-of-done`
- `corp.shadowknight.profile.reviewer`
- `external.shared.policy.ext-policy`
- `user.local.skill.personal-shell`

## Layer Rules

`org/config.toml`:

- may define required corp standards and recommended defaults
- may define minimal unknown-workspace baseline
- may define protected fields and hard safety boundaries
- may not define repo identity such as `repo_class`, `repo_group_id`, or `normalized_remotes`

`repo-groups/<group>/config.toml`:

- may define shared standards and default profiles for a family of repos
- may not define repo identity such as `repo_class`, `repo_group_id`, or `normalized_remotes`

`repos/<repo>/config.toml`:

- must define `normalized_remotes`
- may define `repo_group_id`
- `repo_class` must be `client` or `internal`
- may require or recommend packs and profiles

Local user `config.toml`:

- may define personal contexts, skills, playbooks, packs, profiles, preferences, and workspace bindings
- may enable personal context explicitly
- may not define corp-required completion gates or protected repo identity fields
- may not weaken required corp, repo, or profile policies and completion gates

## Activation

Required standards apply automatically. Optional standards require explicit enablement.

```toml
[activation]
required = [
  "corp.shadowknight.completion_gate.definition-of-done",
  "corp.shadowknight.policy.no-secrets"
]
enabled = [
  "corp.shadowknight.skill.sql-review",
  "corp.shadowknight.context.repo-map"
]
disabled = []
```

Layer configs may also use direct activation lists when a table would be noisy:

- `enabled_skills` -> `activation.enabled`
- `baseline_policies` -> `activation.required`
- `optional_policies` -> `activation.enabled`
- `contexts` -> `activation.enabled`

## Profiles And Jobs

Profiles/jobs are curated work modes. They should be small enough to improve relevance and large enough to include required boundaries.

Example profile:

```toml
id = "reviewer"
title = "Reviewer"
purpose = "Review code changes with security, correctness, and evidence checks."
stop_conditions = ["secrets_detected", "tests_fail_after_two_attempts", "unclear_requirement"]
context_budget = "small"

[activation]
required = [
  "corp.shadowknight.completion_gate.review-before-approve",
  "corp.shadowknight.completion_gate.definition-of-done"
]
enabled = [
  "corp.shadowknight.playbook.pr-review",
  "corp.shadowknight.policy.security-checklist"
]
```

## Materialization

Materialization is strategy-based:

```toml
[materialization]
strategy = "auto" # auto | symlink | junction | hardlink | copy | render-only
```

Use `copy` or `render-only` for workspaces where links are unsafe, unsupported, or likely to leak private source context.

## Skill Promotion Evidence

Do not promote generic skills into corp or repo baselines just because they sound useful. A skill should move out of a local/user layer only when it has evidence for a specific task and a clear applicability boundary.

Add promotion review metadata to skill `item.toml` before promotion:

```toml
[promotion_checklist]
task = "Review Python database migrations"
applicability = "Django 5.x services using PostgreSQL migrations"
evidence = "Caught missing rollback and lock-risk cases in two reviewed PRs"
risks = "Can over-warn for small internal-only tables"
scope = "Only migration review, not general database design"
redundancy = "Complements the definition-of-done completion gate; does not duplicate it"
```

`promote-skills` warns when this checklist or any required field is missing. Treat that warning as a review gate for shared standards: fill in evidence, narrow the skill, or keep it local.

## Source Manifests

Every source manifest must define:

- `id`
- `url`
- `commit`
- `namespace`
- `trust_mode`

Rules:

- `id` must be lowercase ASCII, digits, `_`, `-`
- `commit` must be a Git hash string
- `namespace` must be non-empty
- external/user-imported content defaults to unreviewed until explicitly trusted

## External Skill Trust

Pinned external sources are reproducible, not automatically safe. External skills and imported user skills default to:

```toml
trust_level = "unreviewed"
allows_scripts = false
```

Corp-controlled sources or individual items may be marked after review:

```toml
trust_level = "corp-reviewed"
reviewed_by = "platform-enablement"
reviewed_at = "2026-05-21"
```

`doctor` warns when active external skills remain unreviewed. `allows_scripts = true` is rejected in v1; executable scripts and resources are out of scope for generated skill context.

## Compatibility Metadata

Use compatibility metadata when guidance only applies to specific repo shapes:

```toml
applies_to_languages = ["python"]
applies_to_frameworks = ["django"]
compatible_versions = { django = ">=4.2,<6" }
repo_tags = ["web-api"]
```

Repo, repo-group, org, and profile configs may declare the active context:

```toml
languages = ["python"]
frameworks = ["django"]
framework_versions = { django = "5.0" }
repo_tags = ["web-api"]
```

Resolution warns on likely mismatches. Warnings are advisory in v1; narrow or disable the item when the mismatch is real.

## Completion Gate And Playbook Evidence

Completion gates and playbooks can require explicit completion evidence:

```toml
evidence_required = [
  "tests_run",
  "files_changed_summary",
  "risk_notes",
  "verification_command_output"
]
```

Playbooks can also declare their operating boundary:

```toml
inputs = ["issue", "repo_context"]
outputs = ["patch", "verification_report"]
stop_conditions = ["ambiguous_requirement", "security_boundary_unclear"]
```

Generated `.agents/index.md`, AGENTS.md, and `audit --json` surface active completion gate and playbook evidence requirements before work is called done. `.agents/index.md` also renders active playbook inputs, outputs, and stop conditions. v1 does not execute playbooks or enforce collection automatically.

External tools should consume canonical resolution JSON when they need selected standards, provenance, active playbooks, completion gates, evidence requirements, warnings, or denied items:

```bash
team-agents context --workspace /path/to/repo --profile reviewer --json
```

Tool-specific execution, evidence storage, scheduling, permission enforcement, and task state stay outside `team-agents`.

## Workspace Bindings

Local user `config.toml` may include workspace bindings:

```toml
[[workspace_binding]]
name = "example-non-git"
path = "/abs/path/to/workspace"
repo_group_id = "platform"
disabled_skills = ["corp.shadowknight.skill.repo-onboarding"]
```

Rules:

- `name` and `path` are required
- set `repo_id` or `repo_group_id`, not both
- local suppression must not disable required completion gates or hard safety boundaries

## Validation Workflow

Use:

```bash
PYTHONPATH=src python3 -m team_agents doctor --workspace /path/to/repo --json
```

Use this before `sync` when authoring new corp or user config. It should flag:

- invalid repo layout or source manifests
- missing required completion gates
- unsafe materialization settings
- context quality problems, including too many active items, duplicate contexts/policies, missing verification completion gates, and missing client-data boundaries for client repos
- tracked generated `.agents` content
- tracked router files that may block sync
- workspace resolution failures

Preview a resolution without writing generated files:

```bash
team-agents sync --workspace /path/to/repo --dry-run
```

Inspect active context and provenance:

```bash
team-agents context --workspace /path/to/repo --pretty
team-agents audit --workspace /path/to/repo
team-agents validate --workspace /path/to/repo --json --strict
team-agents registry --json
```

`audit --json` includes a `standards_registry` summary, `sprawl_warnings`, and `context_quality_warnings`. Context quality warnings include remediation text and cover active item count thresholds, broad profile-selected contexts, duplicate contexts/policies, missing verification completion gates, and missing client-data boundaries for client repos. Add `owner`, `maintainer`, `status`, and `review_status` to shared items and profile configs so standards have clear accountability.

`registry --json` lists available contexts, policies, completion gates, skills, playbooks, packs, profiles, and sources across the configured corp and local user layers. Use `--kind`, `--repo-id`, `--profile`, and `--status` to narrow governance and integration views.

CI/governance systems should use `validate --json` for a stable validation report. Schema and resolution failures return nonzero. `--strict` also fails when governance warnings exist. `audit --json --strict` and `doctor --json --strict` use the same warning-strict behavior. The command surface and GitHub Actions example are documented in `docs/specs/v1/ci-governance-command-surface.md`.

`sync` also writes `.agents/artifacts.json`, a machine-readable manifest of generated files. It lists each artifact path, kind, target tool, source resolution hash, intended consumer, description, and whether the file is safe to commit. Client repo generated and router files are marked not safe to commit. The manifest contract is documented in `docs/specs/v1/produced-artifact-manifest.md`.

## Native Source Inputs

External sources may be authored in any of these shapes:

- team-agents native: `<slug>/item.toml` + `<slug>/body.md`
- Claude native: `<slug>/SKILL.md` with frontmatter
- Cursor native: `.cursor/rules/<slug>.mdc` with frontmatter

Native inputs should be normalized into the same resolved standards model before rendering target-specific output.
