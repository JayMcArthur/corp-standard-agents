# Current Context

## Source Of Truth

This repo is now driven by:

1. GitHub PRD issue `#1`: `PRD: team-agents v1 — symlink library, corp-resident user profiles, multi-tool emit, signed-off contracts`
2. The GitHub issue backlog that breaks that PRD into implementable slices

Treat those GitHub issues as the active product memory.

## What Changed

Older in-repo requirements documents described a narrower Codex-first `v1` and an intermediate `v4` correction layer.

Those documents are no longer the active plan.

Current direction is:

- multi-tool from the start: Claude Code, Codex CLI, Cursor
- issue-driven execution from the PRD
- user profiles inside the corp repo
- shared library plus user-global tool seeding
- workspace-local overrides for registered repos
- one canonical freshness/update path

## Rules For Future Work

- Do not treat `docs/requirements/*.md` as the current implementation contract unless they are rewritten to match the PRD and issue backlog.
- Before starting implementation, read PRD issue `#1` and the relevant GitHub issues.
- Prefer updating issues and this file over creating new long-lived speculative design docs.
- Treat old `v1` / `v4` requirements docs as historical notes only.
