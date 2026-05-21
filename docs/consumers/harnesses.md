# Harnesses

Harnesses prepare and supervise model work. They can consume `team-agents` standards as policy and context without asking `team-agents` to run tasks.

## Produces

- task execution state
- local permission prompts
- verification routing
- optional `.agents/episode/` evidence packages
- runtime logs and intervention records

## Consumes

- `team-agents context --workspace <path> --for-harness --json`
- `.agents/resolution.json`
- active contracts and evidence requirements
- active flows as playbooks
- selected profile/job permission notes and stop conditions

## Example Commands And Artifacts

```bash
team-agents context --workspace /path/to/repo --for-harness --json
team-agents audit --workspace /path/to/repo --json
```

```text
.agents/episode/
  task.md
  context-used.json
  verification.md
  risks.md
  decisions.md
```

## Boundaries

`team-agents` supplies constraints and context. Harnesses supply execution, permissions, verification orchestration, episode writes, and runtime intervention handling.
