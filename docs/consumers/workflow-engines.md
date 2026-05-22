# Workflow Engines

Workflow engines such as n8n, LangGraph, and custom orchestrators can consume playbooks and completion gates while keeping execution in their own runtime.

## Produces

- workflow graphs
- node execution
- retries
- schedules
- state persistence
- runtime permission enforcement

## Consumes

- `team-agents context --workspace <path> --profile <profile> --for-workflow-engine --json`
- active playbooks with inputs, outputs, evidence requirements, stop conditions, and owner
- active completion gates selected by the workspace and profile/job
- `.agents/resolution.json` for full provenance
- `team-agents registry --json` for discovery before profile selection

## Example Commands

```bash
team-agents registry --kind playbook --json
team-agents context --workspace /path/to/repo --profile reviewer --for-workflow-engine --json
team-agents audit --workspace /path/to/repo --json
```

## Boundaries

`team-agents` exposes playbooks and completion gates. It does not execute graph nodes, schedule workflows, retry failures, persist runtime state, or define or enforce runtime permissions.
