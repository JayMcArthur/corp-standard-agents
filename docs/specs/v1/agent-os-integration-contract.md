# Agent OS Integration Contract v1

`team-agents` v1 is the standards source for Agent OS products. It exposes resolved standards, provenance, trust metadata, profile/job constraints, contracts, evidence requirements, flow playbooks, and generated target files. It does not manage runtime state.

Agent OS products should consume:

- `team-agents registry --json`: standards catalog across configured corp and local user layers
- `.agents/resolution.json`: primary machine API for resolved workspace context, provenance, active items, warnings, denied items, source trust details, contracts, flow metadata, and generated target outputs
- `team-agents context --workspace <path> --for-agent-os --json`: narrowed Agent OS view of the same resolved context
- generated target files such as `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/team-agents.mdc`

`team-agents` provides:

- standards registry
- resolved profile and job context
- trust and review metadata
- contracts and evidence requirements
- flows as playbooks
- generated target files

Agent OS provides:

- task state
- handoffs
- memory
- scheduling
- runtime permissions
- intervention logs

`context --for-agent-os --json` returns:

- `runtime_boundary`: explicit provider split and non-goals
- `workspace`: repo id, repo group, repo class, selected profile/job, and paths
- `integration_surfaces`: commands and generated files an Agent OS should consume
- `selected_profile_configs`: active profile/job metadata, autonomy notes, approval requirements, stop conditions, and tool-class guidance
- `active_standards`: active skills, policies, docs, contracts, packs, flows, and profiles
- `contracts`: contract titles, activation provenance, and evidence requirements
- `flows_as_playbooks`: flow inputs, outputs, evidence requirements, stop conditions, and activation provenance
- `trust_review_metadata`: per-item trust, review, privacy, lifecycle, source, and activation metadata
- `source_details`: external and corp source trust details from `resolution.json`
- `generated_targets`: active items grouped by emitted tool target
- `warnings` and `denied_items`: advisory and refusal context from resolution

`resolution.json` is sufficient for Agent OS consumption because each active or denied item carries its kind, source, trust and review metadata, activation provenance, privacy status, target outputs, contract evidence keys, and flow inputs/outputs when applicable.

Non-goals:

- no task state
- no handoff state
- no memory store
- no scheduling
- no runtime permission engine
- no intervention log
