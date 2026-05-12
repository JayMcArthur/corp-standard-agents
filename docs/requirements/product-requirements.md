# Product Requirements

## Title

Corporate Agent Overlay System v1

## Purpose

Build a git-backed private agent-overlay system that lets a corporation maintain shared agent skills, policies, private docs, repo mappings, and approved external dependencies outside client codebases, then apply that context safely to any working repo or workspace.

This replaces the broad `v3` direction with a narrower product contract:
- client/project truth stays in the client or project repo when safe
- corporate operational knowledge stays in a separate private control repo
- repo context is discovered automatically for git repos by normalized remote
- local user overrides are supported without weakening corporate safety boundaries
- the first tool target is explicit and concrete: Codex via generated `.agents/` content plus `AGENTS.md` routing behavior

## Problem

Teams want agents to operate with the right private context for each repo without:
- committing private agent infrastructure into client repos
- relying on each developer to copy local setup by hand
- letting arbitrary upstream skill changes flow directly into production use
- forcing every repo to carry the same broad global context

Existing `v3` material identified the right direction, but it remained too broad, under-specified, and too repo-tool-shaped. The first requirements spec needs a stricter product definition.

## Product Summary

The system has four core parts:

1. Corporate control repo
- private git repo cloned locally by users
- contains shared org defaults, repo-group overlays, repo overlays, approved external source registry, and private operational context

2. Repo detection and resolution
- git repos are matched by normalized remote identity
- unknown git repos and non-git folders receive only a minimal org baseline
- non-git workspaces can be manually bound if needed
- repo overlays carry an explicit repo class so safety behavior can differ between `client` and `internal` repos

3. Local user override layer
- optional local repo or folder chosen at setup
- can add personal skills, personal external sources, and preference overrides
- cannot weaken corporate privacy or safety constraints
- to satisfy cross-machine repeatability, setup must support a git-backed user override repo path directly, even though local-only mode remains allowed

4. Generated tool-facing output
- generated locally for the active repo or workspace
- must not leak private corporate operational context into client repos unintentionally
- must use a defined Codex output contract in v1 rather than leaving output shape to implementation-time invention

## Non-Goals For v1

v1 is not:
- a full multi-tool adapter platform
- a general-purpose knowledge base manager
- a live handoff/task/state coordination system
- a package manager for arbitrary third-party skill repo formats
- a git patch/fork management system for upstream skill customization

## Hard Product Rules

1. Private corporate operational context must not be pushed into client repos.
2. Git-backed corp state is the main shared source of truth.
3. Skills are opt-in by resolved config, not auto-loaded broadly.
4. Corporate-approved external sources are pinned to org-approved commits.
5. User overrides can change preferences, not hard safety/privacy boundaries.
6. Resolved context must remain traceable through provenance metadata.
7. Items must carry enforceable privacy metadata, not only prose labels.
8. Generated output and protection behavior must be fully specified before implementation starts.

## Users

### Corporate maintainer

Owns the corporate control repo, approves external updates, defines org defaults, repo-group overlays, repo mappings, and corporate overrides.

### Team member

Clones the corporate control repo, runs setup, works in mapped repos, receives corp updates on sync, and applies optional local overrides.

### Advanced user

Uses personal skills or personal external sources in the local override layer without modifying the shared corporate baseline.

## Primary Use Cases

### 1. Working in a known client repo

The user opens a known git repo. The system identifies it by normalized remote, resolves `org -> repo-group -> repo -> user overrides`, and generates the local tool-facing context safely.

### 2. Working above several sister repos

The user launches an agent from a workspace that spans related repos. The system can apply repo-group context and stable cross-repo relationship docs where configured.

### 3. Working in an unknown folder

The user launches an agent in a random folder or unknown repo. Only the minimal org baseline applies, such as shell/global skills and recommended agent types.

### 4. Receiving corp-approved external skill updates

Corp maintainers update the approved commit for an external source. On next sync, users receive the approved update.

### 5. Personal customization

The user disables a corp-default skill, adds a personal skill, or replaces an inherited item in the user layer without changing shared corp state.

## Information Boundary

### Allowed in client/project repos when safe

- code knowledge
- architecture docs
- requirements
- ADRs
- project specs
- public or project-safe wiki content

### Must stay in the private corporate control repo

- corporate skills
- agent behavior and setup
- internal policies
- internal workflows
- internal playbooks/process
- private repo-specific overlay notes
- approved external-source registry and corp overrides

## Scope For v1

### First-class item kinds

- `skills/`
- `policies/`
- `docs/`

### First-class config layers

- `org`
- `repo-group`
- `repo`
- `user overrides`

### v1 tool target

- Codex-oriented generated output only

### Supported source types

- corp-managed native-format sources
- corp-approved external native-format sources
- user-managed native-format sources

## Resolution Model

### Layer order

`org -> repo-group -> repo -> user overrides`

### Merge behavior

- enabled skills merge additively
- disabled skills subtract from inherited sets
- docs are explicit references only
- baseline policies auto-apply at org level
- optional policies are explicitly referenced
- eligibility filtering uses item metadata before merge

### Hard constraints

Corporate privacy and safety rules remain above user preference overrides.

## Success Criteria

The system succeeds when:
- a user can clone one private corp repo and run setup once
- a known repo automatically resolves to the right corporate overlay on sync
- client repos stay free of private corporate operational material
- corp can approve and roll out external skill updates centrally
- users can customize locally without breaking shared safety rules
- tracked `AGENTS.md` conflicts are handled deterministically and safely
- the on-disk format is explicit enough that a requirements spec can drive implementation directly

## Deferred For Later

- live state packs, handoffs, tasks, and decisions-needed
- adapters for Claude/Cursor/Copilot outputs
- support for non-native third-party skill repo formats
- arbitrary patch/fork workflows for upstream sources
- multi-group repo membership
- fine-grained per-repo approved commit divergence for the same external source
