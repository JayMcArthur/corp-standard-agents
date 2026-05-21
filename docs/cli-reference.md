# CLI Reference

The commands below are the maintained `team-agents` command surface.

## Setup And Lifecycle

```bash
team-agents setup --corp-repo /path/to/corp-control --user-path ~/team-agents-user
team-agents init-corp-repo --dest /path/to/corp-control
team-agents init-user-layer --dest ~/team-agents-user
team-agents update
```

`setup` can initialize missing layers, register a workspace, import local skills with `--import-skills-from`, add a source, and optionally run `sync`.

## Workspace Commands

```bash
team-agents attach --workspace /path/to/repo
team-agents sync --workspace /path/to/repo
team-agents status --workspace /path/to/repo --json
team-agents context --workspace /path/to/repo --pretty
team-agents audit --workspace /path/to/repo
team-agents doctor --workspace /path/to/repo
team-agents validate --workspace /path/to/repo
```

Use `context --json` for the canonical resolution JSON. Use `--for-harness`, `--for-agent-os`, or `--for-workflow-engine` for narrowed integration views.

## Configuration Commands

```bash
team-agents register-repo --workspace /path/to/repo --repo-id internal-app
team-agents onboard-repo --workspace /path/to/repo --repo-class internal
team-agents configure-repo --workspace /path/to/repo --repo-class internal
team-agents configure-group --workspace /path/to/repo --group-id platform
team-agents configure-org --enable-skill corp.example.skill.review
team-agents bind-workspace --path /path/to/repo --repo-id internal-app
team-agents add-source --layer org --source-id shared --url <git-url> --commit <sha> --namespace shared --enable
```

These commands edit layer config and bindings. Required policies, contracts, and packs cannot be weakened by user or workspace additions.

## Library Commands

```bash
team-agents bootstrap-import --source ~/.agents/skills --dest ~/team-agents-user
team-agents promote-skills --from-layer user --to-layer org --skill-id user.local.skill.review
team-agents refresh-personal-skills --source ~/.agents/skills
team-agents complete-skill <skill-id> --workspace /path/to/repo
team-agents registry --json
```

`bootstrap-import` imports native skill folders into a layer. `complete-skill` locally suppresses one-time skills after use.
