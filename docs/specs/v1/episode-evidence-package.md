# Episode Evidence Package v1

Status: Draft
Date: 2026-05-21

## Purpose

The episode evidence package is an external evidence shape for harnesses and human review. It records what the agent was asked to do, which context it used, what changed, what verification ran, what decisions were made, and what risks remain.

`team-agents` v1 defines the shape and tells agents what evidence to collect. It does not orchestrate tasks or enforce runtime submission.

## Location

When produced, an episode evidence package lives under:

```text
.agents/episode/
  task.md
  context-used.json
  verification.md
  risks.md
  decisions.md
```

## Files

`task.md`:

- task summary
- requested outcome
- acceptance criteria
- files or areas expected to change

`context-used.json`:

- active profile/job
- active item ids used during work
- required completion gates
- source and resolution references
- path to `.agents/resolution.json`

`verification.md`:

- commands run
- command outcomes
- relevant output excerpts
- skipped verification with reason

`risks.md`:

- remaining risks
- known limitations
- compatibility or trust warnings considered
- follow-up recommendations

`decisions.md`:

- notable implementation decisions
- alternatives rejected
- user decisions or constraints that shaped the work

## Completion Gate Evidence

Completion Gate `evidence_required` values map to episode files by convention:

- `tests_run` and `verification_command_output`: `verification.md`
- `files_changed_summary`: `task.md`
- `risk_notes`: `risks.md`
- `context_grounding`, `task_decomposition`, and `acceptance_criteria`: `task.md`
- `verification_plan`: `verification.md`

Projects may add domain-specific evidence keys. Unknown keys are allowed in completion gate metadata, but generated guidance should still name them explicitly.

## Non-Goals

- no task runner
- no background orchestration
- no automatic proof validation
- no mandatory write of `.agents/episode/` during `sync`
