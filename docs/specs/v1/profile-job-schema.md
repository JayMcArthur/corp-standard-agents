# Profile/Job Schema v1

Profiles/jobs are activation selectors, not source layers. They can be defined in `profiles/*.toml` by corp, repo-group, repo, or local user layers.

Profile configs use the activation schema fields to select task-specific context. Layers may declare:

- `allowed_profiles`: profile ids that may be selected for the workspace
- `default_profile`: profile id used when no explicit profile is selected
- `autonomy_level`: `interactive`, `supervised`, `background`, or `autonomous`
- `requires_human_approval`: operations that require explicit human approval, such as `file_delete`, `external_send`, `deploy`, or `payment`
- `stop_conditions`: conditions where the agent must stop and escalate, such as `secrets_detected`, `tests_fail_after_two_attempts`, or `unclear_requirement`
- `escalation_contact`: team, person, or channel to contact when a stop condition is hit
- `allowed_tool_classes`: expected tool classes the profile may use, such as `read`, `edit`, or `test`
- `requires_approval_for`: tool classes that require human approval, such as `shell`, `network`, `secrets`, or `deploy`
- `forbidden_tool_classes`: tool classes that must not be used, such as `email-send`, `payment`, or `prod-write`
- `intended_consumers`: consumer types expected to use the profile, such as `human`, `harness`, `agent-os`, `workflow-engine`, or `ci-governance`
- `context_quality_max_active_items`: optional warning threshold for the total active context selected by the profile

Background and autonomous profiles should always declare stop conditions and tool permission notes. Profiles intended for high-risk consumers (`harness`, `agent-os`, or `workflow-engine`) should also declare stop conditions and permission metadata. Profiles that intentionally carry broad context should set `context_quality_max_active_items` explicitly. v1 surfaces these rules in AGENTS.md, context output, audit, and doctor warnings; it does not enforce runtime orchestration.

Selection order is explicit session selection, workspace binding, environment (`TEAM_AGENTS_PROFILE`), then layer default. The machine-readable schema is `schemas/profile-job.schema.json`.
