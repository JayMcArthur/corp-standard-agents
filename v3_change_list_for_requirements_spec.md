# v3 Change List for Requirements Spec

This file is a working critique of [team_agents_private_pack_v3.md](/home/jay/dev/Tools/corporate_standardized_agents/team_agents_private_pack_v3.md:1) against [goal.md](/home/jay/dev/Tools/corporate_standardized_agents/goal.md:1).

Purpose:
- identify where `v3` is going wrong
- capture what must change before implementation
- list possible solution options where this is a product decision, not just an editing fix

Inputs used:
- my direct review of `goal.md` and `team_agents_private_pack_v3.md`
- Claude review thread `cdcd4815-90e0-4bf9-8019-307b508c2775`

## Confirmed Decisions So Far

These were resolved in follow-up discussion and should be treated as current working assumptions for the requirements spec.

### 1. Primary onboarding model

Decision:
- the normal starting path is `git clone` of a full corporate control repo, then run a setup/bootstrap flow

Implication:
- git is the canonical backbone of the system, not just an optional transport

### 2. Core source of truth

Decision:
- a corporate control repo is the main shared source of truth
- one maintained repo can push updates to everyone who uses the system

Implication:
- this is not just "packs plus local bindings"
- the system is centered on a shared org-managed control repo plus local override behavior

### 3. Repo identification

Decision:
- target repos are identified by normalized git remote identity
- SSH and HTTPS forms of the same repo must resolve to the same repo key

Implication:
- local filesystem path is runtime detail only
- corporate mappings should follow the repo across machines and clones

### 4. Repo setup/discovery behavior

Decision:
- when an agent/tool is used on a repo, the setup flow should check whether that repo is already configured in the corporate control repo
- if configured, it should apply corporate defaults plus user overrides

Implication:
- repo onboarding should feel automatic once the corp repo is present locally
- user preferences layer above repo defaults

### 5. User overrides

Decision:
- user overrides should exist as an optional local layer
- setup can create that local override location, and the user can choose where it lives
- users may later copy it or back it with git if they want, but the first spec does not need to require that

Implication:
- corporate defaults remain the main shared contract
- personal customization is supported without forcing a full multi-machine sync design in v1

### 6. Override precedence

Decision:
- user overrides beat repo/corporate defaults for things like preferred skills, disabled skills, and preferred agent types

Implication:
- the final resolution model needs a clear "corp defaults, then local overrides" rule

### 7. Knowledge boundary

Decision:
- project/code/spec knowledge can live in the client or project repo when it is safe to share there
- corporate operational knowledge must stay private

Hard boundary:
- code, specs, architecture, requirements, and project truth may live in the client/project repo
- corporate skills, agent behavior, internal workflows, internal processes, and internal policies must stay in the corporate control repo and must never be pushed into the client repo

Implication:
- this product is primarily a private agent-overlay system, not a general-purpose project knowledge manager

### 8. Private repo-specific overlay content

Decision:
- the corporate control repo may contain private repo-specific notes for a client/project
- examples: internal delivery checklist, private client handling notes, internal working rules for that repo

Constraint:
- this content must be clearly separated from reusable org-wide assets and from public project documentation

### 9. Per-repo mapping shape

Decision:
- use both:
- a central index of repo mappings
- per-repo config files for repo-specific settings

Implication:
- discovery stays simple from one index
- detailed repo behavior can stay modular and easier to maintain

### 10. Skill activation model

Decision:
- skills are opt-in per repo context
- agents working in a repo should only receive the skills explicitly configured for that repo or inherited intentionally from a higher-level mapping

Implication:
- the default model is allowlist, not broad auto-inclusion
- this keeps context tighter and reduces accidental behavior drift

### 11. Agent-type guidance

Decision:
- recommended agent types are useful
- this is primarily about putting the right tools in the right places, not hard restriction, though restrictions may exist in some cases

Implication:
- the spec should support recommended agent types as a first-class field
- hard allow/deny rules should be a separate, optional policy layer

### 12. Sister-repo / repo-group context

Decision:
- sister repos need to be considered because work may begin above a single repo and require awareness of connected repos

Current assumption:
- this should likely be modeled as a grouping layer above individual repo mappings, but it is not yet fully decided

Implication:
- the requirements spec should account for a shared context layer for related repos, not only one isolated repo at a time

### 13. Non-git workspace handling

Decision:
- non-git workspaces are supported, but they are manually bound
- a non-git workspace should still be able to start from a corporate baseline so it is not empty by default

Implication:
- git-backed repos are auto-matched by normalized remote
- non-git workspaces are attached manually to a corp-defined template, profile, or workspace type
- local overrides layer on top in both cases

### 14. Update flow and external skill approvals

Decision:
- corporate updates should flow on next `sync`
- external skills or external packs should be pinned to corp-approved commits
- corporate maintainers should be able to inspect newer upstream updates, approve them, and then roll those approved updates out to everyone else

Implication:
- sync should pull the latest approved corporate state on next run
- the system needs an explicit concept of approved upstream pins for external dependencies
- users should not silently float to the newest upstream version of external skills

### 15. User-owned extensions and bypass path

Decision:
- users may add their own skills outside the corporate baseline
- users may also add remote git-backed skill repos as personal dependencies
- this is the supported bypass path instead of floating corp-managed external dependencies arbitrarily

Implication:
- corp-managed dependencies stay pinned and approved by corp
- user-managed dependencies live in the personal/local layer
- the system needs to distinguish clearly between corp-managed sources and user-managed sources

### 16. Skill-repo interoperability concern

Decision:
- external skill repos may vary in layout and format
- the system may need a parsing/adapter strategy or a standard contract for interoperable skill repos

Implication:
- the requirements spec should decide whether v1 only supports one strict native format or also supports adapter readers for other ecosystems

### 17. v1 skill format posture

Decision:
- v1 should require one strict native skill-pack format
- support for other ecosystems or repo shapes is future adapter/importer work, not part of the first requirements spec

Implication:
- corp-managed and user-managed skill repos both need to follow the same native contract in v1
- research into a few existing popular skill repo patterns can inform future compatibility work, but should not weaken the v1 format requirements

### 18. Inheritance model

Decision:
- inheritance is automatic through `org -> repo-group -> repo`
- local user overrides apply on top
- repos belong to one repo-group only in v1

Implication:
- config resolution stays linear and predictable
- lower layers merge rather than replace by default

### 19. Skill merge behavior

Decision:
- skill resolution uses additive and subtractive merge behavior
- inherited enabled skills merge downward
- disabled skills subtract from inherited sets
- local user overrides can add or disable skills

Implication:
- final active skills are resolved from an allowlist after all layers merge

### 20. Safety boundary for overrides

Decision:
- user overrides may change preferences
- user overrides may not weaken corporate privacy or safety boundaries

Implication:
- the resolver needs hard constraints and soft defaults as separate concepts

### 21. Unknown-location baseline

Decision:
- when an agent is launched in an unknown git repo or a non-git folder, only a minimal org baseline should apply
- this baseline can include things like shell/global skills or recommended agent types
- repo-specific overlays should not apply unless the repo/workspace is explicitly mapped

Implication:
- random folders do not inherit broad project-specific or client-specific private context
- global usefulness is preserved without leaking the rest of the corporate overlay model

### 22. Repo-group content

Decision:
- repo-groups may include curated stable relationship knowledge between sister repos
- repo-groups get their own first-class folder with config plus optional docs

Implication:
- repo-groups are more than a tagging convenience
- they can carry stable cross-repo context without turning into live task memory

### 23. Per-repo overlay structure

Decision:
- per-repo overlays should mirror repo-groups structurally
- each repo overlay gets its own folder with config plus optional private docs

Implication:
- the corp control repo can use a symmetrical structure across org, repo-group, and repo layers

### 24. Central index role

Decision:
- the central index is a lookup helper, not the canonical source of truth
- canonical source of truth lives in the folder configs themselves

Implication:
- avoids duplicated state
- keeps the same mental model across corp config, extensions, and overrides

### 25. Approved external source registry

Decision:
- the corporation maintains a central registry of approved external sources
- each level can opt in or out of those sources
- the same pattern should work for user override sources in the personal layer

Implication:
- approved-source management is centralized
- usage remains selective at `org`, `repo-group`, `repo`, and user override layers

### 26. External source pinning

Decision:
- each approved external source has one corporate-approved commit for the whole organization in v1
- lower layers may opt in or out of the source, but do not pin different approved commits per repo or repo-group

Implication:
- upstream review and rollout stay simple
- version divergence for the same approved source is avoided in v1

### 27. Corporate overrides for external sources

Decision:
- the corporation should be able to overlay or override parts of approved external sources

Implication:
- external sources are not only pinned, they can also be adapted by the corporation without forking the upstream baseline model
- the requirements spec needs to define whether this happens as patch overlays, shadowed items, or a local wrapper layer

### 28. External source customization model

Decision in progress:
- external sources should always be pulled at the approved upstream commit
- the corporation needs a supported way to customize imported items after pull
- full shadowing may be too coarse for small tweaks such as changing a timeout or similar setting

Open design direction:
- prefer the simplest model that supports small controlled modifications without turning v1 into a general patch engine

### 29. v1 external override mechanism

Decision:
- do not use arbitrary git patching, diff application, or fork-merge workflows in v1
- after pulling the approved upstream source, support two override modes:
- field-level overrides for a small approved set of metadata/config fields
- full replacement by canonical id when a small override is not enough

Implication:
- v1 stays simpler and easier to reason about
- future versions may add richer upstream diff/fork workflows, but they are not required for the first requirements spec

### 30. Replacement provenance

Decision:
- when corp fully replaces an upstream item by id, the resolved item must retain provenance back to the original upstream source id and approved commit

Implication:
- reviewers can still trace where the item came from
- corp replacements do not become invisible forks

### 31. User override symmetry

Decision:
- users may apply the same two override modes in their personal layer:
- field overrides for preference-style fields
- full replacement by id when needed

Constraint:
- user changes remain personal
- they never automatically feed back into corp-managed state

### 32. Resolved-item provenance metadata

Decision:
- every resolved item should carry explicit provenance and layering metadata

Minimum metadata:
- canonical id
- source type: `corp`, `external`, or `user`
- source repo/ref or approved commit
- whether it was field-overridden or fully replaced
- which layer performed the override or replacement

Implication:
- debugging resolution and trust issues becomes materially easier

### 33. Canonical item identity

Decision:
- native items use globally unique canonical ids, not source-local ids

Implication:
- override-by-id, replacement, provenance, and diagnostics remain unambiguous across corp, external, and user sources

### 34. New item creation

Decision:
- corp and user layers may define entirely new items, not only override inherited ones

Implication:
- the system is a real source layer, not just a modification layer

### 35. Filesystem-level item kinds

Decision:
- item kinds are distinguished at the filesystem level in v1

Implication:
- repository layout stays human-browsable
- the resolver does not need to infer item kind purely from content

### 36. v1 item kinds

Decision:
- v1 first-class item kinds are:
- `skills/`
- `policies/`
- `docs/`

Explicit non-decisions for v1:
- playbooks are not a separate item kind yet
- agent types stay as config metadata, not standalone items

Implication:
- v1 stays narrower and avoids fake distinctions without runtime value

### 37. Docs activation model

Decision:
- docs are activated by explicit references from org, repo-group, or repo config
- docs are not loaded wholesale by folder presence alone

Implication:
- context bloat is controlled
- docs can exist in the corp control repo without automatically entering every resolved context

### 38. Policy activation model

Decision:
- support both:
- hard baseline policies that auto-apply at org level
- optional policies that are explicitly referenced by org, repo-group, or repo config

Implication:
- hard corporate safety/privacy constraints can be guaranteed everywhere
- narrower or situational policies can still be selectively activated without bloating every context

## Core Read

The goal is narrower and stricter than `v3` currently is.

The goal says:
- reusable private packs
- safe use across any repo
- no private agent infrastructure stored in the client codebase
- repeatable across any machine and any repo

`v3` gets the high-level direction mostly right, but it spreads into too many concepts before the core product contract is nailed down. The main failures are:
- cross-machine repeatability is not actually designed
- privacy protections are described, but not enforced tightly enough
- the MVP is still too large
- several critical behaviors are still ambiguous, which means implementation would end up inventing product rules on the fly

## Must Change Before Writing an Implementation Spec

### 1. Cross-machine repeatability needs a real design

Problem:
- `v3` stores bindings, config, packs, and workspace state under `~/.team-agents/...`
- bindings use absolute local paths
- this does not satisfy the goal requirement to be repeatable across any machine

Why this matters:
- a second machine or second developer will not reliably get the same bindings, lock state, or protection behavior

Change required:
- define a shareable user/team-owned config source, not just local dotfiles

Recommended direction:
- add a private git-backed `profile-pack` or similar for config, bindings, overrides, and workspace lockfiles
- replace binding identity based on `path` with identity based on canonical repo remote or another cross-machine repo id
- keep `path` as a local cache field only

### 2. `sync` must protect the repo before writing anything

Problem:
- `v3` treats `sync` and `protect` as separate actions
- in practice this creates a bad path where `.agents/` is generated before git excludes are installed

Why this matters:
- this is the fastest way to leak private generated context into a client repo

Change required:
- make protection part of `sync`, not a separate safety habit

Recommended direction:
- `sync` must install local excludes idempotently before writing generated files
- in `client` and `strict` modes, `sync` should refuse to write if protection cannot be installed
- `protect` can remain as an alias or inspection command, but not as the main enforcement path

### 3. Trust cannot be declared by the pack itself

Problem:
- `pack.toml` includes `[trust] trusted = true`

Why this matters:
- a malicious or compromised pack can self-attest trust

Change required:
- trust must live in local user/team config, keyed by source identity

Recommended direction:
- pack manifest may request capabilities
- local config grants trust on `pack add`
- trust-on-first-use with stored fingerprint is the cleanest starting point

### 4. Privacy needs enforceable metadata, not just mode descriptions

Problem:
- `v3` has privacy modes, but no concrete per-item metadata model that lets the resolver decide what is allowed

Why this matters:
- rules like "public mode only uses public-safe items" or "client mode blocks certain personal items" are not implementable without item-level metadata

Change required:
- define privacy metadata in item schemas

Recommended direction:
- each item kind should declare at least:
- `id`
- `name`
- `privacy`
- `source pack`
- trust/capability requirements if needed

Practical outcome:
- privacy filtering becomes a real eligibility pass before context composition

### 5. The AGENTS collision rule has to be decided up front

Problem:
- `v3` says not to overwrite tracked `AGENTS.md`
- it proposes `AGENTS.local.md` as a fallback
- Codex will not treat that as the canonical file

Why this matters:
- the current fallback looks safe on paper but fails functionally

Change required:
- pick one actual behavior for tracked `AGENTS.md`

Options:
1. Refuse to sync agent instructions into the repo when `AGENTS.md` is already tracked.
2. Append a managed block to `AGENTS.md` in `personal` or `internal` mode only.
3. Require an explicit external-context invocation path for tools that support it.

Recommended direction:
- append a managed block in `personal` and `internal`
- refuse in `client` and `strict`
- reject `AGENTS.local.md` as the main answer for Codex

### 6. Resolution order and authority order need to be separated cleanly

Problem:
- `v3` has both "Resolution Layers" and "Authority Order"
- both are priority systems, but for different stages

Why this matters:
- readers and implementers will confuse config composition with runtime instruction precedence

Change required:
- rename and separate the stages clearly

Recommended direction:
- `Eligibility`: what privacy/trust rules allow into the candidate set
- `Resolution merge order`: how config and bindings compose the active set
- `Authority precedence`: how conflicting loaded instructions are interpreted at runtime

### 7. The lockfile story must support shared reproducibility without touching the client repo

Problem:
- `v3` puts workspace lockfiles in local home directories and says client repos should keep them local unless approved

Why this matters:
- that defeats reproducibility across machines and teammates

Change required:
- decide where the shared lock actually lives

Recommended direction:
- store workspace locks in the private config/profile pack, keyed by workspace id
- keep code repos clean
- optionally allow an internal-repo committed lock only as an explicit secondary mode

### 8. `pack update` vs `sync` behavior is still too fuzzy

Problem:
- `v3` distinguishes pull from apply, but leaves too much room for interpretation around locked vs latest vs floating behavior

Why this matters:
- if this stays fuzzy, users will not know whether their active context changed after an update

Change required:
- define exact semantics

Recommended direction:
- `pack update` updates pack cache only
- `sync` resolves from lockfile
- `sync --latest` rewrites the lockfile from current pack cache
- avoid floating mode in the first requirements spec unless it is absolutely necessary

### 9. The spec needs actual schemas before implementation

Problem:
- `SKILL.md`, `AGENT.md`, and manifest/frontmatter concepts are referenced repeatedly, but the actual schemas are not properly specified

Why this matters:
- if the spec omits schemas, implementation will invent them implicitly

Change required:
- define the minimal schema for each supported item kind in MVP

Recommended direction:
- for MVP 1, define only the schemas you truly support
- do not define future item kinds loosely and expect the implementation prompt to fill the gaps

### 10. State packs should not be part of MVP 1 requirements

Problem:
- `v3` already pushes state packs to a later MVP, but the document still spends enough time on them that they bleed into the core model

Why this matters:
- writable coordination state has different semantics from read-mostly reusable packs

Change required:
- remove state-pack assumptions from the MVP 1 requirements spec

Recommended direction:
- explicitly defer state packs, handoffs, tasks, and decisions-needed to a later phase
- when they return, model them separately from normal reusable packs

## Recommended Cuts From MVP 1

These are the most useful cuts if the goal is to reach a tight, shippable requirements spec.

Cut:
- state packs
- handoffs
- tasks
- decisions-needed
- optional repo pointer file
- recursive pack dependencies
- profiles, if the first release can work from direct skill enables
- all non-Codex adapters
- subagents
- contracts
- templates
- wiki
- workflows
- playbooks
- checklists
- `pack create`
- `install`
- `setup`
- `public` and `strict` privacy modes if they are not backed by hard enforcement rules yet
- floating update mode

Why:
- each of these adds either unresolved product behavior or extra surface area before the core pack-binding-generation loop is solid

## What the Real MVP Probably Is

If this is meant to become a requirements spec instead of another strategy essay, the smallest coherent MVP looks more like:

- add one or more private/public packs
- bind a repo to a privacy mode and selected skills
- sync generated local agent context
- protect the repo automatically before writes
- show status and health warnings

That is enough to validate:
- private packs outside the code repo
- clean client repos
- repeatable local generation
- workspace-specific agent context

Everything else should justify itself against that core loop.

## Product Decisions You Need To Make Explicitly

### A. How user/team state syncs across machines

Options:
1. Local-only home-directory state.
2. Private git-backed config/profile pack.
3. Hosted/cloud sync.

Recommendation:
- choose private git-backed config/profile pack

Reason:
- it matches the rest of the product model and satisfies the goal without introducing a hosted dependency

### B. What happens when `AGENTS.md` is already tracked

Options:
1. Refuse to sync repo-local agent instructions.
2. Append a managed block in allowed privacy modes.
3. Use a non-canonical local filename.
4. Require external-context invocation.

Recommendation:
- append a managed block in `personal` and `internal`
- refuse in `client`

Reason:
- this is the narrowest path that both works and preserves client safety

### C. Whether TypeScript is the right implementation choice

Options:
1. TypeScript/Node CLI.
2. Go static binary.
3. Rust static binary.

Recommendation:
- if portability is a first-class requirement, re-evaluate TypeScript seriously before the requirements spec implies it is locked in

Reason:
- "any machine" is easier to defend with a single binary than with a Node-based install story

### D. Whether profiles exist in MVP 1

Options:
1. Include profiles immediately.
2. Start with direct enabled-item lists and add profiles later.

Recommendation:
- defer profiles unless they are required to express even the first real-world use case

Reason:
- profiles are helpful, but they are not part of the smallest proof that the core system works

### E. Whether pack dependencies exist in MVP 1

Options:
1. Support recursive pack dependencies immediately.
2. Require explicit pack adds in MVP 1.

Recommendation:
- require explicit pack adds first

Reason:
- recursive dependency resolution turns the tool into a package manager before the core workflow is proven

## Suggested Requirement Reframe

The requirements spec should stop trying to be both:
- a full product vision
- an implementation prompt
- a future roadmap
- a pack taxonomy

Instead, split it into:

1. Product contract
- what problem this solves
- what safety guarantees it must uphold
- what "clean repo" and "repeatable" mean concretely

2. MVP 1 requirements
- exact supported item kinds
- exact commands
- exact data model
- exact protection behavior
- exact lock/update semantics

3. Deferred requirements
- state packs
- team coordination
- non-Codex adapters
- advanced governance

## Bottom Line

`v3` is directionally right, but it is still too broad and too permissive in the wrong places.

The biggest corrections are:
- design cross-machine reproducibility for real
- move privacy and trust from prose into enforceable mechanics
- resolve the `AGENTS.md` collision honestly
- reduce MVP 1 until it is a clean pack/bind/sync/protect/status loop

If those are fixed first, the document becomes a usable foundation for a requirements spec instead of another ambitious concept draft.
