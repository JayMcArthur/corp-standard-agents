# Agent OS

Agent OS products manage agents, tasks, memory, handoffs, scheduling, and runtime permissions while using `team-agents` as the standards source.

## Produces

- task state
- handoffs
- memory updates
- schedules
- runtime permission decisions
- intervention logs

## Consumes

- `team-agents registry --json` for standards discovery
- `team-agents context --workspace <path> --for-agent-os --json` for a narrowed integration view
- `.agents/resolution.json` for full resolved standards and provenance
- generated tool files such as `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/team-agents.mdc`

## Example Commands

```bash
team-agents registry --json
team-agents context --workspace /path/to/repo --for-agent-os --json
team-agents context --workspace /path/to/repo --json
```

## Boundaries

`team-agents` does not store task state, memory, schedules, handoffs, runtime permissions, or intervention logs. Agent OS products own those runtime systems.
