# Team Agents

`team-agents` is a Git-backed standards layer for AI tools.

It lets a team define reusable contexts, policies, completion gates, skills, playbooks, packs, and profiles once, then project the smallest correct subset into Claude Code, Codex CLI, Cursor, and other adapters without committing private standards into client repositories.

## Try It

Build disposable example workspaces and verify the full playbook:

```bash
bash scripts/bootstrap_examples.sh
bash scripts/check_example_flow.sh
```

The example playbook creates a corp standards repo, a local user layer, internal and client workspaces, generated `.agents/` artifacts, and target files such as `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/team-agents.mdc`.

## Install

Install from this checkout:

```bash
bash scripts/install.sh
```

Set up a corp standards repo and a local user layer:

```bash
team-agents init-corp-repo --dest ~/team-agents-standards
team-agents init-user-layer --dest ~/team-agents-user
team-agents setup --corp-repo ~/team-agents-standards --user-path ~/team-agents-user
```

Corp-managed users are available for organizations that want central auditability:

```bash
team-agents setup --corp-repo /opt/corp-control --user alice
```

## Daily Playbook

Attach a workspace, inspect the selected context, then render target files:

```bash
team-agents attach --workspace ~/work/my-project --mode baseline
team-agents context --workspace ~/work/my-project --pretty
team-agents doctor --workspace ~/work/my-project
team-agents sync --workspace ~/work/my-project
```

Personal additions and narrow overrides live in the local user layer:

```toml
# ~/team-agents-user/config.toml
enabled_skills = ["user.local.skill.personal-shell"]
disabled_skills = ["corp.example-org.skill.noisy-helper"]

[[item_override]]
id = "corp.example-org.skill.some-helper"
timeout_seconds = 20
source_note = "Personal timeout override for this machine"
```

Local user overrides may tune optional context or add personal context. They may not disable required corp, repo, or profile policies, completion gates, or packs.

Omit `--mode` from `attach` when you want to choose interactively between repo, group, baseline, and configure-now attachment.

## Author A Standard

Create a skill in a layer such as `~/team-agents-standards/org/skills/review-checklist/`:

```toml
# item.toml
id = "corp.example-org.skill.review-checklist"
kind = "skill"
title = "Review Checklist"
privacy = "repo-safe"
```

```markdown
<!-- body.md -->
Check that the change has tests, clear failure modes, and no private context in generated client-safe files.
```

Enable it in the layer config:

```toml
enabled_skills = ["corp.example-org.skill.review-checklist"]
```

Then run:

```bash
team-agents sync --workspace ~/work/my-project
```

The generated target files include the active skill while preserving provenance and client/privacy safeguards.

## Core Model

Standards are authored in Git-friendly folders:

```text
contexts/         knowledge and context
policies/         rules and guidance
completion_gates/ required behavior, boundaries, definition of done, evidence
skills/           reusable agent capabilities
playbooks/        repeatable human/agent playbooks, not executable automation
packs/            bundles of contexts, policies, completion gates, skills, and playbooks
profiles/         lightweight work modes such as coder, reviewer, support, architect
```

Resolution is layered:

```text
corp -> repo-group -> repo -> profile/job -> local user -> workspace
```

Profiles and jobs are the main anti-bloat mechanism. They select the narrow context set for a work mode instead of loading every available corp or repo standard.

## Command Surface

User commands:

```bash
team-agents attach --workspace /path/to/repo
team-agents sync --workspace /path/to/repo
team-agents status --workspace /path/to/repo --json
team-agents context --workspace /path/to/repo --pretty
team-agents audit --workspace /path/to/repo
team-agents registry --json
team-agents doctor --workspace /path/to/repo
team-agents validate --workspace /path/to/repo
team-agents update
```

Owner and configuration commands:

```bash
team-agents init-corp-repo --dest /path/to/new-corp-control
team-agents init-user-layer --dest ~/team-agents-user
team-agents bootstrap-import --source ~/.agents/skills --dest ~/team-agents-user
team-agents register-repo --workspace /path/to/repo --repo-id internal-app
team-agents onboard-repo --workspace /path/to/repo --repo-class internal
team-agents configure-repo --workspace /path/to/repo --repo-class internal
team-agents configure-group --workspace /path/to/repo --group-id platform
team-agents configure-org --enable-skill corp.example.skill.review
team-agents bind-workspace --path /path/to/repo --repo-id internal-app
team-agents add-source --layer org --source-id shared --url <git-url> --commit <sha> --namespace shared --enable
team-agents promote-skills --source /path/to/source --dest /path/to/layer
team-agents refresh-personal-skills --source ~/.agents/skills
team-agents complete-skill <skill-id> --workspace /path/to/repo
```

Activation is configured in layer `config.toml` files and `profiles/*.toml`. The CLI edits repo/group bindings and source registration; it does not pretend every activation has a dedicated command.

## Outputs

`team-agents sync` produces generated workspace artifacts:

```text
.agents/
  index.md
  resolution.json
  artifacts.json
  skills/
  policies/
  completion_gates/
  contexts/
AGENTS.md
CLAUDE.md
.cursor/rules/team-agents.mdc
```

Primary output artifacts:

- `.agents/resolution.json`: canonical machine-readable resolution artifact
- `.agents/index.md`: human-readable active context and provenance summary
- `.agents/artifacts.json`: generated artifact manifest with commit-safety metadata
- `AGENTS.md`: concise interoperability/router file
- target-native files: compiled outputs for Claude Code, Codex CLI, Cursor, and future adapters

In git repos, `sync` protects generated private context from accidental commits and refuses unsafe output when tracked generated paths would conflict.

## Diagnostics

Use diagnostics to understand what is active and why:

```bash
team-agents context --workspace /path/to/repo --pretty
team-agents audit --workspace /path/to/repo
team-agents registry --json
team-agents doctor --workspace /path/to/repo --json
team-agents validate --workspace /path/to/repo --json
```

`doctor` checks resolution health, profile safety metadata, generated artifact risks, source trust, and common context-quality problems. Run it before `sync`, before committing generated files, and when a workspace does not receive the expected standards.

## Integration Views

`team-agents` is not an orchestrator, harness, task runner, swarm runtime, CRM, inbox automation system, or background workflow engine. It supplies standards, context, provenance, validation, and target-specific rendering.

External runtimes can request narrowed context views:

```bash
team-agents context --workspace /path/to/repo --for-harness --json
team-agents context --workspace /path/to/repo --profile reviewer --for-workflow-engine --json
```

Those views describe constraints and selected context. Runtime execution, scheduling, permissions, task state, handoffs, and intervention logs belong to the consuming runtime.

## Repo Shape

```text
corp-control/
  org/
    config.toml
    contexts/
    policies/
    completion_gates/
    skills/
    playbooks/
    packs/
    profiles/
    sources/
  repo-groups/
  repos/
  indexes/
```

Local user layer:

```text
~/team-agents-user/
  config.toml
  contexts/
  policies/
  completion_gates/
  skills/
  playbooks/
  packs/
  profiles/
  sources/
  workspaces/
```

## Reference

- [Authoring guide](docs/authoring-guide.md)
- [CLI reference](docs/cli-reference.md)
- [Consumer docs](docs/consumers/developers.md)
- [Public specs](docs/specs/v1/item-schema.md)
- [Examples](examples/workspaces/README.md)

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
