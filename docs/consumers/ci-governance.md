# CI Governance

CI, governance, and security systems validate standards and resolved context before unsafe or broken guidance reaches users.

## Produces

- CI pass/fail gates
- governance reports
- security review records
- pull request annotations or artifacts

## Consumes

- `team-agents validate --workspace <path> --json --strict`
- `team-agents audit --workspace <path> --json --strict`
- `team-agents doctor --workspace <path> --json --strict`
- `team-agents registry --json`
- `team-agents context --workspace <path> --json`

## Example Commands

```bash
team-agents validate --workspace "$GITHUB_WORKSPACE" --json --strict
team-agents audit --workspace "$GITHUB_WORKSPACE" --json --strict
team-agents registry --json
team-agents context --workspace "$GITHUB_WORKSPACE" --json
```

## Boundaries

`team-agents` provides validation reports and nonzero exits for failures or strict warnings. CI systems own runners, annotations, artifact upload, secrets policy, and remediation workflows.
