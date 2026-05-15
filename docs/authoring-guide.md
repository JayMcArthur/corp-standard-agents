# Authoring Guide

This guide describes the minimum authoring rules for corp control repos and corp-resident user profiles used by `team-agents`.

## Quick Start

Create starter scaffolds:

```bash
team-agents init-corp-repo --dest /path/to/corp-control
team-agents setup --corp-repo /path/to/corp-control --user alice
```

Then edit the generated files to match your org, repos, sources, and privacy rules.

Recommended first shaping pass:
- `team-agents configure-org --corp-repo /path/to/corp-control`
- `team-agents configure-repo --workspace /path/to/repo`
- `team-agents configure-group --workspace /path/to/repo`

## Folder Shape

Corporate control repo:

```text
corp-agent-control/
  org/
    config.toml
    skills/
    policies/
    docs/
    sources/
  repo-groups/
    <group-id>/
      config.toml
      skills/
      policies/
      docs/
  repos/
    <repo-id>/
      config.toml
      skills/
      policies/
      docs/
  users/
    <username>/
      config.toml
      skills/
      policies/
      docs/
      sources/
  indexes/
    repos.toml
    repo-groups.toml
    sources.toml
```

Corp-resident user profile:

```text
corp-agent-control/users/<username>/
  config.toml
  skills/
  policies/
  docs/
  sources/
```

## Canonical IDs

Every item id must match:

```text
<source-type>.<namespace>.<kind>.<slug>
```

Allowed values:
- `source-type`: `corp`, `external`, `user`
- `kind`: `skill`, `policy`, `doc`
- `namespace`: lowercase ASCII, digits, `_`, `-`
- `slug`: lowercase ASCII, digits, `_`, `-`

Examples:
- `corp.example-org.skill.recursive-planning`
- `external.shared.policy.ext-policy`
- `user.local.skill.personal-shell`

## Layer Rules

`org/config.toml`
- may define baseline skills, policies, docs, minimal unknown-workspace baseline, and protected fields
- may not define `repo_class`, `repo_group_id`, or `normalized_remotes`

`repo-groups/<group>/config.toml`
- may define shared skills, docs, policies, and recommended agent types
- may not define `repo_class`, `repo_group_id`, or `normalized_remotes`

`repos/<repo>/config.toml`
- must define `normalized_remotes`
- may define `repo_group_id`
- `repo_class` must be `client` or `internal`

User profile `config.toml`
- may define personal skills, personal sources, optional policies/docs, preferred agent types, and workspace bindings
- may not define `baseline_policies`
- may not define `repo_class`, `repo_group_id`, or `normalized_remotes` at top level

## Source Manifests

Every source manifest must define:
- `id`
- `url`
- `commit`
- `namespace`
- `trust_mode`

Rules:
- `id` must be lowercase ASCII, digits, `_`, `-`
- `commit` must be a git hash string
- `namespace` must be non-empty

## Workspace Bindings

User profile `config.toml` may include:

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
- `disabled_skills` is optional and currently intended for local one-time skill suppression

## Item Overrides

Item override blocks may only change:
- `enabled`
- `timeout_seconds`
- `recommended_agent_types`
- `tags`
- `source_note`

Example:

```toml
[[item_override]]
id = "external.shared.skill.ext-lint"
timeout_seconds = 77
```

## Validation Workflow

Use:

```bash
PYTHONPATH=src python3 -m team_agents doctor --workspace /path/to/repo --json
```

Use this before `sync` when authoring new corp or user config. It will flag:
- invalid repo layout or source manifests
- tracked generated `.agents` content
- tracked `AGENTS.md` situations that may block sync
- workspace resolution failures

You can also preview a resolution without writing generated files:

```bash
team-agents sync --workspace /path/to/repo --dry-run
```

## Structured Policy Rules

Policy items may optionally declare structured `policy_rules` in `item.toml`.

Example:

```toml
policy_rules = [
  { rule = "required_skill_ids", severity = "fail", skill_ids = ["corp.example-org.skill.recursive-planning"], remediation = "Enable recursive-planning in org/config.toml" },
  { rule = "user_overrides_must_be_git_backed", severity = "warn" }
]
```

Current supported rules:
- `user_overrides_must_be_git_backed`
- `required_skill_ids`
- `forbidden_source_patterns`

Use `team-agents doctor --json` to inspect per-policy compliance entries with severity, detail, and remediation.

## Usage Mode

Items may optionally declare:

```toml
usage_mode = "one-time"
```

Allowed values:
- `reusable`
- `one-time`

Meaning:
- `reusable` skills remain part of steady-state resolution while enabled
- `one-time` skills are intended for setup/onboarding tasks and may be locally suppressed after completion

Completion model:
- registered repos suppress one-time skills at repo scope
- bound paths suppress one-time skills in the workspace binding
- upstream org or repo-group definitions remain unchanged

## Native Source Inputs

External sources may be authored in any of these shapes:
- team-agents native: `<slug>/item.toml` + `<slug>/body.md`
- Claude native: `<slug>/SKILL.md` with frontmatter
- Cursor native: `.cursor/rules/<slug>.mdc` with frontmatter

Current native metadata mappings:
- Claude native: `name`, `description`, optional `model`, optional `tools`
- Cursor native: `description`, optional `globs`, optional `alwaysApply`
