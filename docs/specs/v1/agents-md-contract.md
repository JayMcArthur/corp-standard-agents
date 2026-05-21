# AGENTS.md Contract v1

`AGENTS.md` is the concise workspace interoperability output. It is not a dump of all resolved standards and it is not Codex-only business logic.

The managed block must include:

- workspace identity: repo id, repo group, repo class, and selected profile/job
- pointer to `.agents/index.md` for human-readable expanded context
- pointer to `.agents/resolution.json` for machine-readable provenance, activation reasons, source paths, warnings, and denied items
- required contracts selected for the workspace
- bootstrap or minimal verification guidance when available
- required evidence before done when active contracts or flows declare `evidence_required`
- preparation flow pointers for broad, ambiguous, risky, or multi-file work
- autonomy, approval, stop-condition, and tool-permission notes selected by profiles or active flows
- privacy and generated-output safety boundaries

The managed block must not include:

- full skill bodies by default
- full policy, doc, contract, flow, pack, or profile bodies
- corp-private operational bodies in client repos
- executable orchestration logic

Expanded item bodies stay under `.agents/` when safe for the repo class. Tool-specific renderers may add target-specific wrapping or collision handling, but the AGENTS.md contract content is produced by the generic `agents_md` emitter.
