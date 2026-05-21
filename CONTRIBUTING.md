# Contributing

This repository is maintained as a production-facing package. Public docs should explain how to use, configure, author, validate, or integrate with `team-agents`; they should not contain task lists, PRDs, or completed backlog material.

The repository is currently source-available under a restrictive preview license, not an open-source license.

## Ground Rules

- Preserve the privacy boundary between client-safe and corp-private material.
- Prefer explicit schemas and deterministic failure modes over convenience heuristics.
- Add or update tests for behavior changes.
- Keep generated-output safety and client-repo protections intact unless the public contract is updated with the behavior change.
- Document every retained command in product-facing usage or reference docs.

## Local Workflow

```bash
bash scripts/install.sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash scripts/check_example_flow.sh
```

## Pull Requests

- Keep PRs narrow and explain the user-facing behavior change.
- Include notes about privacy/trust implications when touching resolution or output logic.
- Do not merge changes that weaken tracked-output safety without matching tests and docs.
