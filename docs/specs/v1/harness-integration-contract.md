# Harness Integration Contract v1

`team-agents` v1 exposes constraints for harnesses. It does not run tasks, schedule background work, validate proof automatically, or orchestrate tools.

Harnesses should consume:

- `.agents/resolution.json`: primary machine API for resolved context, provenance, active items, warnings, denied items, and source trust details
- `team-agents context --workspace <path> --for-harness --json`: narrowed runtime view for task harnesses
- `.agents/episode/`: optional evidence package location when an external harness or human writes work evidence

`context --for-harness --json` returns:

- `workspace`: repo id, repo group, repo class, selected profile/job, and paths
- `selected_profile_configs`: active profile/job metadata including autonomy level, permissions, approval requirements, stop conditions, and escalation contact
- `required_contracts`: required active contracts and their evidence requirements
- `active_flows`: active flows with inputs, outputs, evidence requirements, stop conditions, and activation provenance
- `evidence_requirements`: contract and flow evidence keys that must be addressed before work is called done
- `tool_permissions`: profile and flow permission notes for allowed, approval-gated, and forbidden tool classes
- `stop_conditions`: flattened stop conditions from active profiles and flows
- `warnings` and `denied_items`: advisory and refusal context from resolution

Harnesses may use this output to prepare task context, apply local permission prompts, route verification, and write episode evidence. Harnesses must still treat it as guidance and policy context, not an executable workflow definition.

Non-goals:

- no task runner
- no background orchestration
- no automatic proof validation
- no mandatory `.agents/episode/` writes during `sync`
