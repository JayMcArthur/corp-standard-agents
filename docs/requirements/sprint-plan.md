# Sprint Plan

## Goal

Sequence the first implementation work into small deliverables that prove the product contract without dragging `v3` scope back in.

## Delivery Strategy

Build the smallest usable vertical slice first:
- clone corp repo
- detect repo or unknown workspace
- resolve `org -> repo-group -> repo -> user`
- generate safe local output for the first tool target

Everything else should justify itself against that path.

## Sprint -1: Spec Freeze On Safety-Critical Contracts

### Outcomes

- freeze the Codex generated output contract
- freeze `AGENTS.md` collision behavior
- freeze item metadata including privacy fields
- freeze canonical id format
- freeze trust model for corp-approved and user-managed sources
- freeze repo detection rules and multi-remote matching behavior

### Deliverables

- approved output path and `AGENTS.md` rules
- approved `item.toml` schema
- approved source registry schema
- approved remote-normalization examples

## Sprint 0: Finalize Fixtures And Validation Cases

### Outcomes

- create one sample corp control repo fixture
- create one sample user override fixture
- create one known-repo fixture and one unknown-workspace fixture

### Deliverables

- approved requirements docs
- native format examples
- test fixtures for:
- known git repo
- repo-group membership
- unknown git repo
- non-git workspace
- approved external source
- corp replacement of external item
- tracked `AGENTS.md` in an internal repo
- tracked `AGENTS.md` in a client repo
- protection-install failure
- user override that attempts to weaken a corp rule
- duplicate canonical id collision

## Sprint 1: Bootstrap And Repo Loading

### Outcomes

- load corp control repo from local clone
- load user override layer from configured location
- parse explicit folder/config structure
- build indexes from folder truth, not vice versa
- install and validate repo protection logic independently of output generation

### Deliverables

- config loaders for:
- `org/config.toml`
- `repo-groups/*/config.toml`
- `repos/*/config.toml`
- user override config
- item loaders for `item.toml` plus `body.md`
- index readers/builders
- validation errors for malformed layout
- protection installer/checker

### Exit criteria

- sample corp repo loads successfully
- broken config produces useful diagnostics

## Sprint 2: Repo Detection And Layer Resolution

### Outcomes

- normalize git remotes
- match current repo to repo id
- resolve repo-group membership
- support unknown repo / non-git baseline behavior
- merge enabled/disabled sources and skills across layers against a stubbed approved-source registry

### Deliverables

- remote normalization module
- repo matching module
- layer resolver
- baseline policy activation
- explicit doc and optional policy reference resolution

### Exit criteria

- known repo resolves correctly
- unknown repo resolves minimal baseline only
- non-git workspace resolves org baseline plus local overrides
- tracked `AGENTS.md` conflicts are detected before output generation

## Sprint 3: Source Registry And External Pins

### Outcomes

- read approved external source registry
- fetch approved external sources at pinned commits
- keep corp-approved sources separate from user-managed sources

### Deliverables

- source registry parser
- approved source fetch/cache logic
- personal source fetch/cache logic
- provenance model for source origin

### Exit criteria

- corp-approved source pin resolves reproducibly
- user personal source can be added without mutating corp state
- source cache path and validation behavior are exercised

## Sprint 4: Item Resolution And Override Semantics

### Outcomes

- support direct items, field overrides, and full replacements
- carry provenance through the resolved graph
- enforce hard corporate safety/privacy boundaries
- emit machine-readable resolution output as soon as provenance exists

### Deliverables

- canonical id model
- item merger
- field-override engine for approved fields
- full replacement-by-id logic
- provenance record output

### Exit criteria

- corp can replace an external item while retaining upstream provenance
- user can override preference fields without weakening hard constraints
- resolution output shows per-item provenance and eligibility decisions

## Sprint 5: Generated Output And Protection

### Outcomes

- generate first tool-target output
- refuse unsafe writes when protection cannot be established

### Deliverables

- sync command
- generated output writer
- resolution summary output

### Exit criteria

- known repo generates local context safely
- client/private operational context does not get written unsafely
- unknown locations still get minimal useful output
- internal tracked `AGENTS.md` managed-block updates work correctly
- client tracked `AGENTS.md` conflicts fail correctly

## Sprint 6: Diagnostics And Usability

### Outcomes

- make the system explain what it did
- show why a skill, doc, or policy is present or absent
- show provenance and override history

### Deliverables

- status command
- doctor command
- resolution report
- validation and warning surfaces
- safety warnings for tracked/generated conflicts

### Exit criteria

- a user can understand the active context without reading internal code

## Deferred Backlog After MVP Slice

- playbook-specific runtime treatment
- multi-tool adapters
- importers for third-party skill repo formats
- live state/handoff model
- advanced external-source diff/fork workflows
- richer non-git workspace templates

## Immediate Build Order

If implementation starts now, the first concrete steps should be:

1. Freeze `item.toml`, source-registry, generated-output, and `AGENTS.md` collision rules.
2. Create fixture corp control repo structure and negative-case fixtures in this project.
3. Define config schemas for `org`, `repo-group`, `repo`, item metadata, and user override layers.
4. Implement repo detection and normalized remote matching across multiple remotes.
5. Implement layer merge for sources, skills, docs, and policies.
6. Add provenance-rich resolution output before adding fancy generation behavior.
