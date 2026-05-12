# Authoring Guide

This guide describes the minimum authoring rules for corp control repos and user override layers used by `team-agents`.

## Quick Start

Create starter scaffolds:

```bash
team-agents init-corp-repo --dest /path/to/corp-control
team-agents init-user-overrides --dest /path/to/user-overrides
```

Then edit the generated files to match your org, repos, sources, and privacy rules.

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
  indexes/
    repos.toml
    repo-groups.toml
    sources.toml
```

User overrides:

```text
user-overrides/
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
- `corp.shadowknight.skill.shell-global`
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

User `config.toml`
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

User override `config.toml` may include:

```toml
[[workspace_binding]]
name = "example-non-git"
path = "/abs/path/to/workspace"
repo_group_id = "platform"
```

Rules:
- `name` and `path` are required
- set `repo_id` or `repo_group_id`, not both

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
