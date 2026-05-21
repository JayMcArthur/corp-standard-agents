# Developers

Developers consume resolved standards in their working repos and may add local user preferences without weakening corp-required context.

## Produces

- local user-layer docs, skills, flows, packs, profiles, and workspace bindings
- explicit personal activations
- work evidence when a profile, contract, or flow asks for it

## Consumes

- generated `.agents/index.md`
- generated `.agents/resolution.json`
- generated tool files such as `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/team-agents.mdc`
- `team-agents context --workspace <path> --json` for resolved context
- `team-agents doctor --workspace <path>` for local setup and governance warnings

## Example Commands

```bash
team-agents init-user-layer --dest ~/team-agents-user
team-agents setup --corp-repo /path/to/corp-control --user-path ~/team-agents-user
team-agents attach --workspace /path/to/repo
team-agents sync --workspace /path/to/repo
team-agents doctor --workspace /path/to/repo
```

## Boundaries

Developers may add personal context and choose profiles. They may not disable corp-required policies, contracts, or packs, weaken corp-private privacy, or use `team-agents` as a task manager, background agent, or automation runtime.
