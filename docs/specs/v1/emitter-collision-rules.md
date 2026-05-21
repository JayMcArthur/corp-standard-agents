# Emitter Collision Rules v1

Generated workspace files are managed locally and should not be committed.

Rules:

- `.agents/` is generated output.
- Router files are `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/team-agents.mdc`.
- Existing managed blocks are replaced in place.
- Internal repos may append a managed block to tracked router files.
- Client repos refuse tracked router files without managed block markers.
- Tracked `.agents/` content blocks sync.
