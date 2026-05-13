# Team Agents

`team-agents` is a local CLI for applying a private corporate agent overlay to a repo or workspace without committing private agent infrastructure into client codebases.

## Install

```bash
bash scripts/install_local.sh
```

That creates a local virtualenv and installs the `team-agents` CLI in editable mode without requiring registry access.

## Commands

```bash
team-agents setup --corp-repo /path/to/corp-control --user-overrides /path/to/user-overrides
team-agents setup --corp-repo /path/to/corp-control --user-overrides /path/to/user-overrides --workspace /path/to/repo --repo-id my-repo --repo-class internal --sync
team-agents sync --workspace /path/to/repo
team-agents sync --workspace /path/to/repo --dry-run
team-agents status --workspace /path/to/repo --json
team-agents doctor --workspace /path/to/repo
team-agents init-corp-repo --dest /path/to/new-corp-control
team-agents init-user-overrides --dest /path/to/new-user-overrides
team-agents bootstrap-import --source ~/.agents/skills --dest ~/.team-agents-user
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
  indexes/
    repos.toml
    repo-groups.toml
    sources.toml
```

The product requirements and technical contract live in [docs/requirements/product-requirements.md](/home/jay/dev/Tools/corporate_standardized_agents/docs/requirements/product-requirements.md:1) and [docs/requirements/technical-requirements.md](/home/jay/dev/Tools/corporate_standardized_agents/docs/requirements/technical-requirements.md:1).

Authoring rules for corp repos and user overrides live in [docs/authoring-guide.md](/home/jay/dev/Tools/corporate_standardized_agents/docs/authoring-guide.md:1).

## Output

`team-agents sync` generates local-only Codex context into:

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

## Trust

- Corp-managed external sources are pinned to explicit commits.
- Optional manifest fingerprints are verified when present.
- User-managed remote sources use local trust-on-first-use records under the cache root unless a manifest fingerprint is provided.
- `status --json`, `doctor --json`, and `.agents/resolution.json` expose source trust and fingerprint metadata.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

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

The normal product path is the CLI, not a custom script. For a local workstation bootstrap that also imports existing Codex skills:

```bash
bash scripts/install_local.sh

team-agents setup \
  --corp-repo ~/.team-agents-corp \
  --user-overrides ~/.team-agents-user \
  --cache-root ~/.team-agents/cache \
  --init-corp-if-missing \
  --init-user-if-missing \
  --import-skills-from ~/.agents/skills \
  --import-skills-to user
```

If you also want first-run repo registration and initial generated output in one command:

```bash
team-agents setup \
  --corp-repo ~/.team-agents-corp \
  --user-overrides ~/.team-agents-user \
  --cache-root ~/.team-agents/cache \
  --init-corp-if-missing \
  --init-user-if-missing \
  --import-skills-from ~/.agents/skills \
  --import-skills-to user \
  --workspace /path/to/repo \
  --repo-id my-repo \
  --repo-class internal \
  --add-and-enable-source repo shared-ext https://github.com/acme/native-skills.git <sha> shared \
  --sync
```

That flow will:
- use the locally installed CLI
- scaffold `~/.team-agents-corp` if missing
- scaffold `~/.team-agents-user` if missing
- import non-system skills from `~/.agents/skills`
- import them into `user`, `org`, or `repo`
- import adjacent text resources as optional docs in the target layer
- write `~/.team-agents/config.toml`
- optionally register the current repo in the corp control repo
- optionally register and enable native-format remote git sources
- optionally run the first `sync`

Recommended lifecycle:
- bootstrap import into `user` first
- promote shared skills into `org` or `repo`
- leave only true personal preferences in `user`

Example normalization step:

```bash
team-agents promote-skills --from-layer user --to-layer org --all-imported
```

`bootstrap-import` is intended as a first-run migration path. It is not the long-term source of truth. After import, the managed items live natively in your corp or user layers.

The helper script is only a thin convenience wrapper around the same CLI flow:

```bash
bash scripts/setup_jay_local.sh
```

## License

This repo is source-available, not open source.

It currently uses the restrictive preview license in [LICENSE](/home/jay/dev/Tools/corporate_standardized_agents/LICENSE:1). Third-party production/commercial use requires prior written permission.
