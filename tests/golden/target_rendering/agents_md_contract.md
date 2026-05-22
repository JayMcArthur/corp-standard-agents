# Project Agent Guidance

- Repo: `api`
- Repo group: `platform`
- Repo class: `internal`
- Active profile/job: `coder`

Generated context lives under `.agents/`. Read `.agents/index.md` first, and use `.agents/resolution.json` for provenance, activation reasons, and source paths.

## Required Completion Gates
- `corp.example.completion_gate.definition-of-done`: Definition Of Done
- `corp.example.completion_gate.repo-bootstrap`: Repo Bootstrap

## Minimal Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Preparation For Complex Work
For broad, ambiguous, risky, or multi-file work, use the active preparation playbook before implementation:
- `corp.example.playbook.prep-before-code`: Prep Before Code

## Safety
- Treat `.agents/` and this managed block as generated local context.
- Do not commit generated private context unless the repo explicitly tracks it by policy.

Expanded skills, policies, contexts, completion gates, playbooks, packs, and profile details stay in `.agents/`; this file stays concise.
