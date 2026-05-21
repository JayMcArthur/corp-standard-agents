# Workflow Engine Integration Contract v1

`team-agents` v1 exposes flows and contracts for workflow engines without becoming a workflow executor. n8n, LangGraph, custom orchestrators, and CI workflow systems may consume the resolved standards and decide how to execute their own graph.

Workflow engines should consume:

- `team-agents context --workspace <path> --profile <profile> --for-workflow-engine --json`: narrowed view for active flows, contracts, selected profile/job context, evidence requirements, and stop conditions
- `.agents/resolution.json`: primary machine API for the full resolved context and item provenance
- `team-agents registry --json`: standards catalog when a workflow needs discovery before selecting a profile/job

Flow items support the structured metadata workflow engines need:

- `owner` and `maintainer`
- `inputs`
- `outputs`
- `evidence_required`
- `stop_conditions`
- autonomy and approval metadata when declared

Workflow engines may select a profile or job with `--profile <profile>`. The resolved output then includes the active flows and contracts selected by that profile/job plus any required repo or corp standards.

`context --for-workflow-engine --json` returns:

- `runtime_boundary`: explicit provider split and non-goals
- `workspace`: repo id, repo group, repo class, selected profile/job, and paths
- `integration_surfaces`: commands and generated files a workflow engine should consume
- `selected_profile_configs`: active profile/job metadata and safety constraints
- `active_contracts`: active contract titles, owners, activation provenance, and evidence requirements
- `flows`: active flow playbook metadata, including owners, inputs, outputs, evidence requirements, stop conditions, approval guidance, and activation provenance
- `evidence_requirements`: flattened contract and flow evidence keys
- `stop_conditions`: flattened profile/job and flow stop conditions
- `warnings` and `denied_items`: advisory and refusal context from resolution

`team-agents` provides:

- flow playbook metadata
- resolved profile and job context
- active contracts
- evidence requirements
- stop conditions
- trust and review metadata through `resolution.json`

Workflow engines provide:

- workflow graph
- node execution
- retries
- scheduling
- state persistence
- runtime permission enforcement

Non-goals:

- no workflow execution
- no graph runtime
- no scheduler
- no retry engine
- no state persistence
