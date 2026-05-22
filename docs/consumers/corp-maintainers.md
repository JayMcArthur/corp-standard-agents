# Corp Maintainers

Corp maintainers own the standards repo. They publish reusable policies, completion gates, contexts, skills, playbooks, packs, profiles, repo registry entries, source pins, and governance defaults.

## Produces

- `org/`, `repo-groups/`, and `repos/` layer content
- activation defaults and protected fields in `config.toml`
- reviewed external source pins in `sources/*.toml`
- packs and profiles for common work modes
- CI governance reports from `validate`, `audit`, and `registry`

## Consumes

- `team-agents validate --json --strict` for schema and governance validation
- `team-agents registry --json` for catalog and ownership review
- `team-agents audit --workspace <path> --json` for resolved workspace provenance
- `.agents/resolution.json` to confirm what downstream consumers receive

## Example Commands

```bash
team-agents init-corp-repo --dest ./corp-control
team-agents validate --workspace /path/to/repo --json --strict
team-agents registry --json
team-agents audit --workspace /path/to/repo --json
```

## Boundaries

Corp maintainers define standards and governance. They do not use `team-agents` as a task runner, workflow executor, memory store, scheduler, or hosted governance service.
