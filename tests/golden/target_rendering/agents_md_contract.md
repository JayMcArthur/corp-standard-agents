# Project Agent Guidance

- Repo: `api`
- Repo group: `platform`
- Repo class: `internal`
- Active profile/job: `coder`

Generated context lives under `.agents/`. Read `.agents/index.md` first, and use `.agents/resolution.json` for provenance, activation reasons, and source paths.

## Required Contracts
- `corp.example.contract.definition-of-done`: Definition Of Done
- `corp.example.contract.repo-bootstrap`: Repo Bootstrap

## Minimal Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Preparation For Complex Work
For broad, ambiguous, risky, or multi-file work, use the active preparation flow before implementation:
- `corp.example.flow.prep-before-code`: Prep Before Code

## Safety
- Treat `.agents/` and this managed block as generated local context.
- Do not commit generated private context unless the repo explicitly tracks it by policy.

Expanded skills, policies, docs, contracts, flows, packs, and profile details stay in `.agents/`; this file stays concise.
