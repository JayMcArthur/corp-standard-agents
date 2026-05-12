# Contributing

This project is still in early product-shaping mode. Expect fast changes to the on-disk format and CLI behavior.

The repository is currently source-available under a restrictive preview license, not an open-source license.

## Ground Rules

- Keep changes aligned with the requirements in `docs/requirements/`.
- Preserve the privacy boundary between client-safe and corp-private material.
- Prefer explicit schemas and deterministic failure modes over convenience heuristics.
- Add or update tests for behavior changes.

## Local Workflow

```bash
bash scripts/install_local.sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash scripts/check_example_flow.sh
```

## Pull Requests

- Keep PRs narrow and explain the user-facing behavior change.
- Include notes about privacy/trust implications when touching resolution or output logic.
- Do not merge changes that weaken tracked-output safety or client-repo protections without a spec update.
