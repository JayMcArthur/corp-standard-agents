# Maintainer Context

`team-agents` is a Git-backed standards layer for AI tools.

It answers:

> What is the smallest correct set of company, repo, profile, and user context this AI tool should receive for this work?

Then it projects that context into target tools such as Claude Code, Codex CLI, Cursor, and integration views for external runtimes.

## Product Boundary

`team-agents` supplies standards, selected context, provenance, validation, generated target files, and public contract shapes.

It does not execute work, schedule tasks, manage handoffs, enforce runtime permissions, store memory, run workflows, or act as an Agent OS.

## Maintained Direction

- Standards are the central object, not agents.
- Source standards live in Git-friendly `docs/`, `policies/`, `contracts/`, `skills/`, `flows/`, `packs/`, and `profiles/`.
- Layer order is `corp -> repo-group -> repo -> profile/job -> local user -> workspace`.
- The local user layer is the default user model.
- Corp-managed user profiles remain an explicit compatibility mode.
- Optional skills, packs, docs, policies, contracts, and flows are opt-in.
- Profiles and jobs select minimal work-mode context and prevent bloat.
- Materialization is strategy-based, not symlink-only.
- `.agents/resolution.json` is the primary machine-readable API.
- `.agents/artifacts.json`, `.agents/index.md`, `AGENTS.md`, `CLAUDE.md`, and Cursor rules are generated outputs.

## Engineering Rules

- Keep docs product-facing: usage, examples, public contracts, and maintained references only.
- Do not add task lists, PRDs, roadmap packets, or completed issue archives to the product docs.
- Do not make symlinks the only freshness or materialization path.
- Do not activate optional items merely because files exist.
- Do not require personal user context to live in the corp repo.
- Do not let user or workspace additions weaken required corp/repo/profile policies or contracts.
- Runtime-facing metadata is standards context; external runtimes own enforcement.
- Prefer resolver tests and contract tests before broad refactors.
