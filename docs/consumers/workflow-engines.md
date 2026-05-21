# Workflow Engines

Workflow engines such as n8n, LangGraph, and custom orchestrators can consume flows and contracts while keeping execution in their own runtime.

## Produces

- workflow graphs
- node execution
- retries
- schedules
- state persistence
- runtime permission enforcement

## Consumes

- `team-agents context --workspace <path> --profile <profile> --for-workflow-engine --json`
- active flows with inputs, outputs, evidence requirements, stop conditions, owner, and approval metadata
- active contracts selected by the workspace and profile/job
- `.agents/resolution.json` for full provenance
- `team-agents registry --json` for discovery before profile selection

## Example Commands

```bash
team-agents registry --kind flow --json
team-agents context --workspace /path/to/repo --profile reviewer --for-workflow-engine --json
team-agents audit --workspace /path/to/repo --json
```

## Boundaries

`team-agents` exposes flow playbooks and contracts. It does not execute graph nodes, schedule workflows, retry failures, persist runtime state, or enforce runtime permissions.
