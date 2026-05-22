# Produced Artifact Manifest v1

`team-agents sync` writes `.agents/artifacts.json` so humans, CI, harnesses, workflow engines, and downstream tooling can inspect which files were generated and what each file is for.

Top-level fields:

- `schema_version`: `v1`
- `workspace`: workspace root used for relative artifact paths
- `repo_class`: resolved repo class
- `source_resolution_hash`: SHA-256 hash of the resolved `resolution.json` payload used to produce the artifacts
- `artifacts`: generated artifact entries

Each artifact entry includes:

- `path`: path relative to the workspace root
- `kind`: artifact category such as `context-index`, `resolution`, `artifact-manifest`, `skill`, `policy`, `context`, `bootstrap-guidance`, or `tool-router`
- `target`: target tool for router files, such as `codex`, `claude`, or `cursor`; otherwise null
- `generated_by`: command producer, currently `team-agents sync`
- `source_resolution_hash`: hash tying the artifact to the resolved context
- `safe_to_commit`: whether the generated file is expected to be committed in this repo
- `consumer`: intended consumer such as `machine`, `human-and-agent`, `codex`, `claude`, or `cursor`
- `description`: short purpose statement

Manifest coverage includes:

- `.agents/index.md`
- `.agents/resolution.json`
- `.agents/artifacts.json`
- generated `.agents/skills/`, `.agents/policies/`, and `.agents/contexts/` files
- `.agents/bootstrap.md` when bootstrap guidance is active
- tool-native router files such as `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/team-agents.mdc`

Safety rules:

- `.agents/**` generated files are not safe to commit.
- Client repo router files are not safe to commit.
- Untracked router files are not safe to commit because sync adds them to Git exclude.
- Internal repo router files are safe to commit only when the repo already tracks them and managed-block collision rules are satisfied.

Non-goals:

- no artifact upload
- no CI artifact storage
- no provenance signing
- no runtime execution manifest
