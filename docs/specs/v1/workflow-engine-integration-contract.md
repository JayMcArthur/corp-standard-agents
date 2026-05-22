# Workflow Engine Integration Contract v1

`team-agents` v1 exposes playbooks and completion gates for workflow engines without becoming a workflow executor. n8n, LangGraph, custom orchestrators, and CI workflow systems may consume the resolved standards and decide how to execute their own graph.

Workflow engines should consume:

- `team-agents context --workspace <path> --profile <profile> --for-workflow-engine --json`: narrowed view for active playbooks, completion gates, selected profile/job context, evidence requirements, and stop conditions
- `.agents/resolution.json`: primary machine API for the full resolved context and item provenance
- `team-agents registry --json`: standards catalog when a workflow needs discovery before selecting a profile/job

Playbook items support the structured metadata workflow engines need:

- `owner` and `maintainer`
- `inputs`
- `outputs`
- `evidence_required`
- `stop_conditions`

Workflow engines may select a profile or job with `--profile <profile>`. The resolved output then includes the active playbooks and completion gates selected by that profile/job plus any required repo or corp standards.

`context --for-workflow-engine --json` returns:

- `runtime_boundary`: explicit provider split and non-goals
- `workspace`: repo id, repo group, repo class, selected profile/job, and paths
- `integration_surfaces`: commands and generated files a workflow engine should consume
- `selected_profile_configs`: active profile/job metadata and safety constraints
- `active_completion_gates`: active completion gate titles, owners, activation provenance, and evidence requirements
- `playbooks`: active playbook metadata, including owners, inputs, outputs, evidence requirements, stop conditions, and activation provenance
- `evidence_requirements`: flattened completion gate and playbook evidence keys
- `stop_conditions`: flattened profile/job and playbook stop conditions
- `warnings` and `denied_items`: advisory and refusal context from resolution

`team-agents` provides:

- playbook metadata
- resolved profile and job context
- active completion gates
- evidence requirements
- stop conditions
- trust and review metadata through `resolution.json`

Workflow engines provide:

- workflow graph
- node execution
- retries
- scheduling
- state persistence
- runtime permission policy and enforcement

Non-goals:

- no workflow execution
- no graph runtime
- no scheduler
- no retry engine
- no state persistence
