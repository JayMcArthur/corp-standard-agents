# Technical Requirements

## Goal

Define the native repository format, resolution behavior, sync behavior, and override rules for v1 of the corporate agent overlay system.

## Native Repository Shape

The corporate control repo is explicit and verbose by design.

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

The indexes are lookup helpers only. Canonical truth lives in each folder's `config.toml` and item files.

Minimum index schemas:

```toml
# indexes/repos.toml
[[repo]]
id = "client-acme-web"
path = "repos/client-acme-web"

# indexes/repo-groups.toml
[[repo_group]]
id = "acme-platform"
path = "repo-groups/acme-platform"

# indexes/sources.toml
[[source]]
id = "shared-ts-skills"
path = "org/sources/shared-ts-skills.toml"
```

## Native Item Format

Every v1 item uses the same explicit folder shape.

```text
skills/
  <slug>/
    item.toml
    body.md

policies/
  <slug>/
    item.toml
    body.md

docs/
  <slug>/
    item.toml
    body.md
```

External native-format sources and user-managed native-format sources must use the same item structure.

## Local User Override Shape

The user override layer is separate from tracked corp config. Its location is chosen during setup.

Example:

```text
~/.team-agents-user/
  config.toml
  skills/
  policies/
  docs/
  sources/
  workspaces/
```

In v1, this may be plain local files or a user-managed git repo. The system must not require sync of this layer to function.

For cross-machine repeatability, setup must support a git-backed user override repo path directly. Local-only mode is supported, but only the git-backed mode is expected to reproduce the same personal layer across machines.

## Local Setup Config

`team-agents setup` writes a local machine config file at:

```text
~/.team-agents/config.toml
```

Minimum keys:
- `corp_repo_path`
- `user_override_path`
- `cache_root`
- `default_tool_target`

This file points to the corp control repo clone and the chosen user override location. It is not the same thing as the user override content repo/folder itself.

## Config Files

### `org/config.toml`

Defines:
- org id
- org baseline enabled sources
- org baseline enabled skills
- org disabled skills
- baseline auto-applied policies
- optional policy references
- optional doc references
- recommended agent types for unknown locations
- privacy and safety rules

### `repo-groups/<group-id>/config.toml`

Defines:
- repo-group id
- member repo ids
- enabled and disabled sources
- enabled and disabled skills
- optional policy references
- optional doc references
- recommended agent types

### `repos/<repo-id>/config.toml`

Defines:
- canonical repo id
- normalized remote match data
- optional repo-group reference
- repo class: `client` or `internal`
- enabled and disabled sources
- enabled and disabled skills
- optional policy references
- optional doc references
- recommended agent types
- repo-specific restrictions if needed

### User override config

Defines:
- personal sources
- enabled and disabled skills
- policy or doc opt-ins where allowed
- preferred agent types
- workspace-local bindings for non-git contexts

## Canonical IDs

Every item must have a globally unique canonical id.

The system must support:
- unambiguous override-by-id
- unambiguous replacement-by-id
- provenance across corp, external, and user layers

Example shape:

```text
corp.shadowknight.skill.typescript-review
external.some_source.policy.secrets
user.jay.skill.shell_helper
```

Canonical id format is fixed for v1 as:

```text
<source-type>.<source-namespace>.<kind>.<slug>
```

Rules:
- `source-type` is one of `corp`, `external`, `user`
- `kind` is one of `skill`, `policy`, `doc`
- `slug` uses lowercase ASCII plus dashes or underscores
- ids are globally unique within the fully qualified string

## Item Kinds

v1 supports exactly:
- `skills/`
- `policies/`
- `docs/`

Item kinds are represented by filesystem location, not inferred dynamically.

## Item Metadata

Each item must carry enough metadata to support provenance and resolution.

Minimum required metadata:
- canonical id
- kind
- title or name
- source type: `corp`, `external`, `user`
- source repo/ref or approved commit
- privacy: `corp-private` or `repo-safe`

Resolved items must additionally record:
- whether they were inherited directly, field-overridden, or fully replaced
- which layer performed the override or replacement
- upstream source provenance when a corp or user replacement shadows an inherited external item

### `item.toml` schema

Each `item.toml` MUST define:
- `id`
- `kind`
- `title`
- `privacy`

Optional common fields:
- `tags`
- `recommended_agent_types`
- `timeout_seconds`
- `source_note`

`body.md` holds the human-readable item content used in generated output.

## External Sources

### Approved external source registry

Org maintains a central registry of approved external sources.

Each source entry must include:
- source id
- source url
- approved commit hash
- source namespace
- trust mode
- optional signing or fingerprint metadata

### External source usage

- org can enable approved sources by default
- repo-group and repo layers can opt in or subtract them
- user layer can add personal sources separately

### Approved pin model

In v1, each approved external source has one org-wide approved commit. Different repos do not pin different approved commits for the same approved source.

### Trust model

For corp-approved external sources:
- the corporate control repo is the trust anchor
- each source is resolved from a specific approved commit hash
- fetched content must match the approved commit hash exactly

For user-managed personal sources:
- the user override config is the trust anchor
- personal sources must be declared explicitly by url and pinned commit hash
- setup may record trust-on-first-use metadata locally

## Override Model

### Supported override modes

For inherited items, corp and user layers may:

1. Apply field-level overrides for a small approved set of fields.
2. Fully replace an inherited item by canonical id.

### v1 field override set

The exact list should stay small. Initial fields:
- enabled or disabled state where relevant
- timeout or execution limit metadata
- recommended agent types
- tags or classification
- short instruction header metadata

Content body patching is not supported in v1. Full replacement is used instead.

### Hard boundary

User overrides may not weaken corp privacy or safety rules.

## Repo Detection

### Git repos

Git repos are matched by normalized remote identity across all configured remotes.

Normalization rules for v1:
- lowercase the host
- strip scheme/user credentials/port where equivalent
- normalize scp-style ssh and URL-style ssh to the same host/path form
- trim a trailing `.git`
- trim trailing `/`
- preserve path case by default
- allow host-specific path lowercasing rules for known case-insensitive hosts such as `github.com`

The matcher must inspect all remotes in the current repo. If any normalized remote alias matches a configured repo entry, that repo is a candidate. If multiple repo entries match, resolution fails with an explicit error.

### Unknown git repos

If no repo mapping exists, apply only the minimal org baseline.

### Non-git workspaces

Non-git workspaces are manual in v1.

Behavior:
- inherit the minimal org baseline by default
- can be saved into local user overrides as named workspace bindings
- do not automatically gain repo-specific overlays unless explicitly bound

## Repo Groups

Repo groups are first-class folders with config and optional docs.

They can contain:
- shared source/skill policy
- recommended agent types
- stable relationship docs between sister repos

They may not be used as live task-state containers in v1.

Each repo belongs to at most one repo group in v1.

## Resolution Algorithm

### Eligibility stage

Before merge, filter disallowed items by:
- hard corporate privacy and safety rules
- repo class
- item privacy metadata

Rules:
- `corp-private` items may never be written into client repo generated output as raw corp operational material outside the approved output contract
- `repo-safe` items may be included where explicitly referenced
- user overrides that attempt to weaken a denied eligibility decision must fail

Protected org-level fields:
- `baseline_policies` are not user-disable-able
- org safety/privacy rules are not user-disable-able
- any later protected corp field must be explicitly marked as protected in schema rather than assumed

### Merge stage

Resolve:
- enabled sources
- disabled sources
- enabled skills
- disabled skills
- referenced docs
- referenced optional policies
- baseline policies
- recommended agent types

Order:

`org -> repo-group -> repo -> user overrides`

### Final output stage

Build the final active allowlist and generate tool-facing output plus a machine-readable resolution record.

Conflict rules:
- duplicate canonical ids within the same layer are an error
- index disagreements with folder truth are an error
- missing referenced items are an error unless explicitly marked optional in a later version

## Policy Activation

Two policy classes:

1. Baseline policies
- auto-applied at org level

2. Optional policies
- explicitly referenced by org, repo-group, repo, or user config where allowed

## Docs Activation

Docs are never included by folder presence alone.

Docs must be explicitly referenced from config.

## Sync Behavior

### Required behavior

`sync` is the main operational command and must:
- refresh and read the local corp control repo working state
- read the approved external source registry
- fetch or refresh approved external sources at approved commits
- resolve context for the current repo or workspace
- install repo protection before writing generated output where applicable
- write generated output
- emit resolution/provenance diagnostics

### Update model

Corp-approved changes flow to users on next sync.

Users do not automatically float to upstream external changes outside corp-approved pins.

If a fetched external source does not contain the approved commit hash exactly, sync must fail hard and refuse to use the source.

## Protection Behavior

Before writing repo-local generated output in a git repo, `sync` must ensure local protection is active.

At minimum:
- install `.git/info/exclude` entries before writing
- never modify tracked `.gitignore` for this purpose
- refuse to write if protection cannot be installed
- avoid overwriting tracked user files unexpectedly

### Generated output contract for Codex

For a git-backed repo or non-git workspace, the resolved output path is:

```text
<workspace>/
  .agents/
    index.md
    resolution.json
    skills/
      <slug>/SKILL.md
    policies/
      <slug>.md
    docs/
      <slug>.md
```

And one repo-root `AGENTS.md` file is managed for Codex routing.

Rules:
- if `AGENTS.md` is untracked or absent, `sync` may create a generated router file and must protect it locally in git repos
- if repo class is `internal` and `AGENTS.md` is already tracked, `sync` appends or updates only a managed block between fixed markers
- if repo class is `client` and `AGENTS.md` is already tracked, `sync` must refuse repo-local output and explain the conflict explicitly
- generated `AGENTS.md` content must only route to local `.agents/` content and warn not to commit generated agent context

Privacy-to-output rules:

| Repo class | Output path | Allowed body materialization |
|---|---|---|
| `internal` | `.agents/skills/`, `.agents/policies/`, `.agents/docs/` | `corp-private` and `repo-safe` allowed |
| `internal` | `AGENTS.md` managed block | routing text only |
| `client` | `.agents/skills/`, `.agents/policies/`, `.agents/docs/` | `repo-safe` only |
| `client` | `AGENTS.md` managed block or generated router | routing text only |
| `client` | `resolution.json` | provenance for both classes allowed, but must not embed full `corp-private` bodies |

Meaning:
- in `client` repos, `corp-private` item bodies must never be written to `.agents/` files
- `corp-private` items may still appear in `resolution.json` as metadata and provenance only
- if a required skill or policy only exists as `corp-private`, sync must fail for `client` repos rather than materialize it unsafely

### Managed block markers

When updating a tracked internal `AGENTS.md`, the managed block markers are:

```text
<!-- team-agents:start -->
<!-- team-agents:end -->
```

`sync` may edit only content inside those markers.

### Resolution record

`resolution.json` is a machine-readable record written at:

```text
<workspace>/.agents/resolution.json
```

It MUST include:
- matched repo id or unknown status
- matched repo-group id, if any
- active repo class
- enabled sources
- enabled skills
- active policies
- active docs
- recommended agent types
- per-item provenance and override status
- safety warnings

For `corp-private` items in `client` repos, `resolution.json` must include metadata only and must not inline full content bodies.

## Unknown-Location Baseline

When launched in an unknown repo or random folder, the system applies:
- minimal org baseline skills
- recommended agent types

It must not apply:
- client-specific overlays
- repo-group docs
- repo-specific private operational context

For v1, the minimal org baseline MUST be defined explicitly in `org/config.toml` as a small allowlist intended for unknown locations.

For non-git workspaces, no git protection step exists. The workspace is treated as local-only, and sync may write generated output directly.

## Required Diagnostics

The system must be able to show:
- matched repo id or unknown status
- matched repo-group, if any
- enabled sources
- disabled sources
- enabled skills
- active policies
- active docs
- recommended agent types
- item provenance and override status
- safety-related warnings

## CLI Surface Required For v1

The minimum command surface is:
- `team-agents setup`
- `team-agents sync`
- `team-agents status`
- `team-agents doctor`

Required meanings:
- `setup` selects or creates the user override location and records the corp control repo path
- `sync` performs resolution, protection, and generation
- `status` prints the resolved context summary
- `doctor` validates layout, trust, protection, and conflict state

## Source Cache

External source cache location for v1:

```text
~/.team-agents/cache/sources/<source-id>/<approved-commit>/
```

Rules:
- cache is local implementation detail, not canonical state
- repeatability comes from the corp repo plus pinned commits, not from the cache itself
- stale cache entries may be deleted safely if not currently referenced

## Explicitly Deferred

- multi-tool output adapters beyond the first target
- arbitrary git patch or fork merge workflows for external source customization
- live state coordination
- support for non-native external repo formats
