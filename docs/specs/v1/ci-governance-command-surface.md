# CI Governance Command Surface v1

`team-agents` v1 exposes stable JSON commands for CI, governance, and security systems. These commands validate the standards repo and resolved workspace context without installing a runtime.

Recommended CI commands:

```bash
team-agents validate --workspace . --json
team-agents validate --workspace . --json --strict
team-agents audit --workspace . --json
team-agents registry --json
team-agents context --workspace . --json
```

`validate --json` returns:

- `schema_version`: `v1`
- `kind`: `governance-validation`
- `status`: `ok` or `fail`
- `strict`: whether warning-strict mode was requested
- `workspace`: resolved workspace path
- `errors`: schema, loading, resolution, doctor, policy, or completion gate failures
- `warnings`: governance warnings from doctor checks and resolution warnings
- `strict_failure`: true when `--strict` turned warnings into a failure
- `resolution`: matched repo, repo group, profile, repo class, and resolution warnings when resolution succeeds
- `doctor_summary` and `doctor_checks`: doctor summary and check details when doctor ran

Exit behavior:

- schema or config violations return nonzero
- resolution failures return nonzero
- doctor failures return nonzero
- `--strict` returns nonzero when governance warnings exist
- non-strict warnings keep `status = "ok"` and exit zero

`audit --json --strict` returns nonzero when audit governance warnings exist. Audit warnings include resolution warnings, sprawl warnings, and context-quality warnings.

`doctor --json --strict` returns nonzero when any doctor warning or failure exists. Without `--strict`, doctor returns nonzero only on failures.

GitHub Actions example:

```yaml
name: team-agents-governance

on:
  pull_request:

jobs:
  validate-standards:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure team-agents
        run: |
          team-agents setup \
            --corp-repo "$GITHUB_WORKSPACE" \
            --user-path "$HOME/team-agents-user"
      - name: Validate governance context
        run: team-agents validate --workspace "$GITHUB_WORKSPACE" --json --strict
      - name: Export registry
        run: team-agents registry --json
      - name: Export resolved context
        run: team-agents context --workspace "$GITHUB_WORKSPACE" --json
```

Non-goals:

- no CI runner implementation
- no hosted governance service
- no automatic remediation
- no workflow execution
