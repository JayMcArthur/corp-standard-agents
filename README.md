# Team Agents

`team-agents` is a local CLI for applying a private corporate agent overlay to a repo or workspace without committing private agent infrastructure into client codebases.

Current repo memory and target direction live in [CONTEXT.md](/home/jay/dev/Tools/corporate_standardized_agents/CONTEXT.md:1) and GitHub issue `#1`.

Unless explicitly stated otherwise, the command examples in this README describe the current implementation surface, not the final target-state product design.

## Install

```bash
bash scripts/install.sh
team-agents setup --corp-repo /path/to/corp-control --user alice
```

This is the only supported install + setup path. It:
- creates `~/.team-agents/venv`
- installs `team-agents` in editable mode from this checkout
- writes the `team-agents` wrapper to `~/.local/bin/team-agents`
- leaves machine-specific state creation to `team-agents setup`

To remove the wrapper and virtualenv without deleting local state:

```bash
bash scripts/uninstall.sh
```

## Commands

```bash
bash scripts/install.sh
team-agents setup --corp-repo /path/to/corp-control --user alice
team-agents setup --corp-repo /path/to/corp-control --user alice --workspace /path/to/repo --repo-id my-repo --repo-class internal --sync
team-agents sync --workspace /path/to/repo
team-agents sync --workspace /path/to/repo --dry-run
team-agents audit --workspace /path/to/repo
team-agents context --workspace /path/to/repo --pretty
team-agents status --workspace /path/to/repo --json
team-agents doctor --workspace /path/to/repo
team-agents update
team-agents onboard-repo --workspace /path/to/repo --repo-class internal --repo-group-id platform --enable-skill corp.example-org.skill.shell-global
team-agents bind-workspace --path /path/to/non-git-workspace --repo-group-id platform
team-agents refresh-personal-skills --source ~/.agents/skills
team-agents migrate-user-overrides --user alice --corp-repo /path/to/corp-control
team-agents init-corp-repo --dest /path/to/new-corp-control
team-agents init-user-overrides --dest /path/to/new-user-overrides
team-agents bootstrap-import --source ~/.agents/skills --dest /path/to/corp-control/users/alice
team-agents promote-skills --from-layer user --to-layer org --all-imported
team-agents add-source --layer org --source-id shared-ext --url /path/or/git/url --commit <sha> --namespace shared --enable
```

## Control Repo Shape

```text
corp-agent-control/
  org/
    config.toml
    skills/
    policies/
    docs/
    sources/
  repo-groups/
    <group-id>/
      config.toml
      skills/
      policies/
      docs/
  repos/
    <repo-id>/
      config.toml
      skills/
      policies/
      docs/
  users/
    <username>/
      config.toml
      skills/
      policies/
      docs/
      sources/
  indexes/
    repos.toml
    repo-groups.toml
    sources.toml
```

Current product memory lives in [CONTEXT.md](/home/jay/dev/Tools/corporate_standardized_agents/CONTEXT.md:1).

The active PRD is GitHub issue `#1`: `PRD: team-agents v1 — symlink library, corp-resident user profiles, multi-tool emit, signed-off contracts`.

The files under `docs/requirements/` are historical and must not be treated as the current source of truth unless they are explicitly rewritten to match the PRD and issue backlog.

Authoring rules for corp repos and user overrides live in [docs/authoring-guide.md](/home/jay/dev/Tools/corporate_standardized_agents/docs/authoring-guide.md:1).

## Output

`team-agents setup --user <name>` seeds user-global outputs into:

```text
~/.claude/skills/<slug>/SKILL.md
~/.codex/AGENTS.md
~/.cursor/rules/<slug>.mdc
```

`team-agents sync` generates workspace-local context into:

```text
.agents/
  index.md
  resolution.json
  skills/
  policies/
  docs/
AGENTS.md
```

In git repos, `sync` installs local exclude protection before writing and refuses unsafe output when tracked generated paths would conflict.

Minimum supported Cursor version:
- user-global `.cursor/rules/` support is required for the default Cursor emitter path
- older Cursor versions may still work with workspace-local rules after `sync`, but the user-global default surface is unsupported

## Trust

- Corp-managed external sources are pinned to explicit commits.
- Optional manifest fingerprints are verified when present.
- User-managed remote sources use local trust-on-first-use records under the cache root unless a manifest fingerprint is provided.
- `status --json`, `doctor --json`, and `.agents/resolution.json` expose source trust and fingerprint metadata.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Corp Policy Compliance

Policy items can carry structured `policy_rules` in `item.toml`. `team-agents doctor --json` reports per-policy compliance entries with severity, detail, and remediation hints for the current machine/workspace.

## Example Bootstrap

The repo includes a checked-in example control repo, user override layer, and upstream external source under [examples/](/home/jay/dev/Tools/corporate_standardized_agents/examples).

To materialize disposable local workspaces and machine config:

```bash
bash scripts/bootstrap_examples.sh
```

By default this writes a disposable runtime under `/tmp/team-agents-example-env` so the example non-git workspace does not accidentally inherit this repository's own `.git` root.

That script will:
- create a runtime tree under `/tmp/team-agents-example-env/`
- initialize a pinned example external source git repo
- create example internal, client, unknown, and non-git workspaces
- create an isolated virtualenv and run the CLI from `PYTHONPATH=src`
- write `~/.team-agents/config.toml` under the script-managed example `HOME`

You can validate the full example flow with:

```bash
bash scripts/check_example_flow.sh
```

## Local Onboarding

Canonical flow:

```bash
bash scripts/install.sh
team-agents setup --corp-repo /path/to/corp-control --user alice
```

If you also want first-run repo registration and workspace materialization in one command:

```bash
team-agents setup \
  --corp-repo /path/to/corp-control \
  --user alice \
  --workspace /path/to/repo \
  --repo-id my-repo \
  --repo-class internal \
  --sync
```

Recommended lifecycle:
- bootstrap import into `user` first
- promote shared skills into `org` or `repo`
- leave only true personal preferences in `user`
- use `team-agents update` as the canonical refresh command

`bootstrap-import` is a migration path. After import, the managed items live natively in corp or user layers.

## Guided Repo Operations

After install, the normal operational commands should be:

```bash
team-agents sync
team-agents audit
team-agents context --pretty
```

To onboard an unknown git repo into the corp control repo:

```bash
team-agents onboard-repo \
  --workspace /path/to/repo \
  --repo-class internal \
  --repo-group-id platform \
  --enable-skill corp.example-org.skill.shell-global
```

To refresh imported personal local skills from `~/.agents/skills`:

```bash
team-agents refresh-personal-skills
```

To bind a non-git workspace to a repo or repo-group:

```bash
team-agents bind-workspace --path /path/to/folder --repo-group-id platform
```

`register-repo` still exists as a lower-level command, but `onboard-repo` is the primary user-facing onboarding flow.

## License

This repo is source-available, not open source.

It currently uses the restrictive preview license in [LICENSE](/home/jay/dev/Tools/corporate_standardized_agents/LICENSE:1). Third-party production/commercial use requires prior written permission.
