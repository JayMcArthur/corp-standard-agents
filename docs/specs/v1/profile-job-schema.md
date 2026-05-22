# Profile/Job Schema v1

Profiles/jobs are activation selectors, not source layers. They can be defined in `profiles/*.toml` by corp, repo-group, repo, or local user layers.

Profile configs use the activation schema fields to select task-specific context. Layers may declare:

- `allowed_profiles`: profile ids that may be selected for the workspace
- `default_profile`: profile id used when no explicit profile is selected
- `stop_conditions`: conditions where the agent must stop and escalate, such as `secrets_detected`, `tests_fail_after_two_attempts`, or `unclear_requirement`
- `intended_consumers`: consumer types expected to use the profile, such as `human`, `harness`, `workflow-engine`, or `ci-governance`
- `context_quality_max_active_items`: optional warning threshold for the total active context selected by the profile

Profiles intended for integration consumers (`harness` or `workflow-engine`) should declare stop conditions. Profiles that intentionally carry broad context should set `context_quality_max_active_items` explicitly. v1 surfaces these rules in AGENTS.md, context output, audit, and doctor warnings; it does not enforce runtime orchestration or permission policy.

Selection order is explicit session selection, workspace binding, environment (`TEAM_AGENTS_PROFILE`), then layer default. The machine-readable schema is `schemas/profile-job.schema.json`.
