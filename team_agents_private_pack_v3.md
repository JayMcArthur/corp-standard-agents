# Team Agents v3: Private Pack + Universal Skill Manager

> Superseded by the requirements set under [docs/requirements/](/home/jay/dev/Tools/corporate_standardized_agents/docs/requirements/product-requirements.md:1). Keep this file as historical context, not the active implementation spec.

## Core Correction

The project/client repo should **not** be the main storage location for private skills, policies, workflows, playbooks, handoffs, or agent knowledge.

Many repos may be:

- Client-owned
- Public
- Contractor-accessible
- Shared with people who should not see our internal agent infrastructure
- Simple projects where we do not want to pollute the repo

So the system should work like this:

```text
Private agent pack repos contain the reusable agent infrastructure.
Local workspace bindings decide which packs apply to which repo.
Generated agent context is local-only by default.
The code repo can stay clean.
```

This also makes the tool useful for anyone.

A solo developer can install it and use only skills.

A team can use it for shared skills, workflows, policies, and project context.

An agency can use it across client repos without leaking private process.

A company can use it to standardize how agents work across projects.

---

# Product Identity

This is not just a repo tool.

This is:

```text
A local agent pack manager for personal, team, client, and project AI context.
```

It should support a maturity ladder:

## Level 1: Personal Skills

User installs the tool and enables skills globally.

```text
~/.team-agents/packs/core/
~/.team-agents/config.toml
```

Use case:

> “I want my coding agents to always have my Python, TypeScript, SQL, and Git helper skills.”

## Level 2: Project Bindings

User maps a local repo to a profile.

```text
When working in /dev/client-site, use client-work + web-dev.
```

Use case:

> “This repo should use my web-dev skills and client-safe workflow, but I do not want anything committed to the repo.”

## Level 3: Team Packs

A team shares private packs through git.

```text
company-agent-pack/
  skills/
  policies/
  playbooks/
  checklists/
```

Use case:

> “Everyone on the team gets the same agent behavior when working on company projects.”

## Level 4: Client/Project Packs

Client-specific or project-specific knowledge lives in private packs, not the client repo.

```text
acme-agent-pack/
foursouls-agent-pack/
vidafy-agent-pack/
```

Use case:

> “Agents need to know this client/project context, but we do not want to ship it in the client’s code repo.”

## Level 5: Coordination Layer

Teams use private state packs for handoffs, tasks, decisions-needed, and project memory.

```text
workspace-state-pack/
  acme/
    handoffs/
    tasks/
    decisions-needed/
```

Use case:

> “Agents do not share memory, but they can share git-backed private context.”

---

# Final Mental Model

```text
Packs are the source of truth.
Bindings decide where packs apply.
Generated files are local/tool-facing output.
Code repos stay clean by default.
```

---

# What We Pull from dotagents

Sentry dotagents has good ideas:

- `agents.toml`
- `agents.lock`
- Git dependencies
- Repeatable installs
- Tool-facing `.agents` output
- Skills/subagents as packages
- Locking exact versions

We should reuse the concepts, not necessarily the exact product direction.

Our system is different because it focuses on:

- Personal and team deployment
- Private packs outside client repos
- Workspace bindings
- Profiles
- Privacy modes
- Project/client packs
- Private coordination state
- Skills as one feature, not the whole product
- Agent context beyond subagents

---

# Core Architecture

```text
Remote git packs
  ↓
Local pack cache
  ↓
Global config + workspace bindings
  ↓
Resolved active context
  ↓
Local generated tool output
```

Example:

```text
git@github.com:shadowknight/core-agent-pack.git
git@github.com:shadowknight/team-agent-pack.git
git@github.com:shadowknight/acme-agent-pack.git
  ↓
~/.team-agents/packs/
  ↓
~/.team-agents/config.toml
~/.team-agents/bindings.toml
  ↓
/client/acme-site/.agents/       # generated, local ignored
/client/acme-site/AGENTS.md      # generated local if safe
```

---

# Code Repo vs Agent Pack Repo

## Code Repo

The real project.

```text
client-site/
  src/
  package.json
  README.md
```

Default: no private agent files committed.

## Agent Pack Repo

Private git repo.

```text
shadowknight-agent-pack/
  pack.toml
  profiles/
  skills/
  policies/
  workflows/
  playbooks/
  contracts/
  wiki/
  checklists/
  templates/
  subagents/
```

## Workspace Binding

Local-only mapping.

```text
~/.team-agents/bindings.toml
```

Example:

```toml
[[workspace]]
id = "acme-site"
path = "/home/jay/dev/acme-site"
packs = ["shadowknight", "acme"]
profiles = ["client-work", "web-dev"]
privacy = "client"
```

## Generated Output

Tool-facing files generated locally.

```text
client-site/.agents/
client-site/AGENTS.md
```

These should be excluded locally with `.git/info/exclude`.

---

# Pack Types

The system should support multiple pack types.

## 1. Core Pack

General reusable public or private skills.

```text
core-agent-pack/
```

Examples:

- Git helper
- TypeScript helper
- Python helper
- SQL helper
- Docker helper
- Security review skill

## 2. Personal Pack

User’s private preferences and skills.

```text
personal-agent-pack/
```

Examples:

- My coding style
- My preferred shell commands
- My standard project setup
- My favorite stack templates

## 3. Team Pack

Company/team-wide practices.

```text
shadowknight-agent-pack/
```

Examples:

- Team coding standards
- Client work policy
- Before-delivery checklist
- PR review playbook
- Secrets policy
- Standard workflows

## 4. Client Pack

Private client-specific context.

```text
acme-agent-pack/
```

Examples:

- Client architecture notes
- Client preferences
- Known client environment issues
- Client-specific playbooks
- Delivery checklist
- Private handoffs

## 5. Project Pack

Private project/product-specific context.

```text
foursouls-agent-pack/
```

Examples:

- Four Souls engine contract
- Card DSL skill
- Game state architecture
- Deployment playbook
- Project ADRs

## 6. State Pack

Volatile coordination context.

```text
workspace-state-pack/
```

Examples:

- Active handoffs
- Current tasks
- Decisions needed
- Investigation notes
- Workstream status

Recommended separation:

```text
Stable reusable context -> core/team/project packs
Volatile coordination context -> state pack
```

---

# Private Pack Layout

```text
shadowknight-agent-pack/
  pack.toml
  README.md

  profiles/
    default.toml
    web-dev.toml
    ai-automation.toml
    client-work.toml
    internal-product.toml

  skills/
    typescript-helper/
      SKILL.md
    python-helper/
      SKILL.md
    sql-helper/
      SKILL.md
    client-communication-helper/
      SKILL.md

  policies/
    agent-safety.md
    secrets-policy.md
    client-data-policy.md
    no-private-context-in-client-repo.md

  workflows/
    branch-strategy.md
    client-delivery.md
    code-review.md

  playbooks/
    add-feature.md
    fix-bug.md
    review-pr.md
    debug-production-issue.md
    onboard-client-repo.md

  contracts/
    agent-editing-boundaries.md
    client-repo-boundaries.md

  wiki/
    team-overview.md
    glossary.md
    common-errors.md
    preferred-tools.md

  checklists/
    before-commit.md
    before-client-delivery.md
    end-of-task.md
    security-review.md

  templates/
    adr-template.md
    handoff-template.md
    task-template.md

  subagents/
    security-reviewer/
      AGENT.md
    pr-reviewer/
      AGENT.md
```

---

# Pack Manifest: `pack.toml`

```toml
id = "shadowknight"
name = "Shadow Knight Agent Pack"
version = "1.0.0"
type = "team"

[[depends]]
id = "core"
type = "git"
url = "git@github.com:shadowknight/core-agent-pack.git"
ref = "main"

[[depends]]
id = "security"
type = "git"
url = "git@github.com:shadowknight/security-agent-pack.git"
ref = "main"

[defaults]
profile = "default"

[trust]
trusted = true
allow_scripts = "ask"
```

When someone pulls/updates this pack, dependencies should be pulled recursively.

---

# Profiles

Profiles are bundles of enabled context.

Example:

```toml
# profiles/client-work.toml

id = "client-work"
name = "Client Work"

[enabled]
skills = [
  "core.git-helper",
  "core.typescript-helper",
  "shadowknight.client-communication-helper"
]

policies = [
  "shadowknight.agent-safety",
  "shadowknight.secrets-policy",
  "shadowknight.client-data-policy",
  "shadowknight.no-private-context-in-client-repo"
]

playbooks = [
  "shadowknight.add-feature",
  "shadowknight.fix-bug",
  "shadowknight.before-client-delivery"
]

checklists = [
  "shadowknight.before-commit",
  "shadowknight.security-review",
  "shadowknight.end-of-task"
]
```

Profiles make the product useful quickly.

A new user can just do:

```bash
team-agents profile use web-dev
```

or bind a repo:

```bash
team-agents bind --profile client-work --profile web-dev
```

---

# Local Global Config

```toml
# ~/.team-agents/config.toml

[user]
name = "Jay"
default_privacy = "client"

[[pack]]
id = "core"
url = "git@github.com:shadowknight/core-agent-pack.git"
ref = "main"

[[pack]]
id = "shadowknight"
url = "git@github.com:shadowknight/shadowknight-agent-pack.git"
ref = "main"

[defaults]
packs = ["core", "shadowknight"]
profiles = ["default"]

[generated]
default_target = "repo-local"
protect_with_git_exclude = true
```

---

# Workspace Binding

```toml
# ~/.team-agents/bindings.toml

[[workspace]]
id = "playfoursouls"
path = "/home/jay/dev/playfoursouls"
name = "Four Souls Digital"
packs = ["core", "shadowknight", "foursouls"]
profiles = ["internal-product", "web-dev"]
privacy = "internal"
project = "playfoursouls"

[[workspace]]
id = "acme-site"
path = "/home/jay/dev/acme-site"
name = "Acme Website"
packs = ["core", "shadowknight", "acme"]
profiles = ["client-work", "web-dev"]
privacy = "client"
client = "acme"
```

This is the main repo opt-in mechanism.

It keeps client repos clean.

---

# Optional Repo Pointer File

Sometimes a repo can safely include a pointer.

Example:

```toml
# team-agents.project.toml

version = 1
workspace_hint = "playfoursouls"
allowed_public = false

[recommended]
packs = ["core", "shadowknight", "foursouls"]
profiles = ["internal-product", "web-dev"]
```

This file contains no private instructions.

It only says which private packs/profiles should be used.

For client repos, default should be no pointer file.

---

# Privacy Modes

Privacy modes should be first-class.

## Personal

For local-only personal projects.

```text
Can use personal and private packs.
May generate repo-local files.
Usually local-only.
```

## Internal

For company-owned repos.

```text
Can use team/project packs.
May commit pointer files.
Generated .agents usually ignored.
```

## Client

For client repos.

```text
No private context committed.
Use local workspace binding.
Generate local files only.
Strong warning before staging generated context.
```

## Public

For open source repos.

```text
Only public-safe packs.
No private wiki/handoffs/client notes.
No private policies.
```

## Strict

For sensitive repos.

```text
No repo writes unless explicit.
Generate outside repo if possible.
No scripts.
No user overrides.
No private context in working tree unless explicitly allowed.
```

---

# Protecting Client Repos

Default protection for client mode:

```text
1. Do not write team-agents.toml into repo.
2. Do not commit .agents/.
3. Do not overwrite tracked AGENTS.md.
4. Add generated files to .git/info/exclude.
5. Warn if .agents or AGENTS.md are staged.
6. Prefer AGENTS.local.md when AGENTS.md exists.
7. Do not store handoffs/tasks in client repo.
```

Command:

```bash
team-agents protect
```

Adds local-only excludes:

```gitignore
# team-agents generated private context
.agents/
AGENTS.md
AGENTS.local.md
.team-agents.local/
```

Only add `AGENTS.md` if it is not already tracked.

---

# Generated Output Options

## Option A: Repo-local generated output

```text
repo/.agents/
repo/AGENTS.md
```

Most compatible with agent tools.

Risk: accidental commit.

Mitigation:

```text
Use .git/info/exclude
Warn before staging
Health check
```

## Option B: Repo-local generated output with local AGENTS file

```text
repo/.agents/
repo/AGENTS.local.md
```

Safer if `AGENTS.md` is tracked by client.

Tool support may vary.

## Option C: Outside-repo generated output

```text
~/.team-agents/workspaces/<workspace-id>/generated/
```

Safest.

Least compatible with tools that only scan repo-local `.agents`.

Recommendation:

```text
Default to Option A with local git exclude.
Use Option B if AGENTS.md is tracked.
Use Option C for strict mode.
```

---

# Agent-Facing Router

Generated `AGENTS.md` should be a router, not the full context.

Example:

```markdown
# Agent Instructions

This workspace uses locally generated Team Agents context.

Read:

1. `.agents/index.md`
2. `.agents/policies/`
3. `.agents/contracts/`
4. Relevant `.agents/playbooks/`
5. Relevant `.agents/skills/`

Do not commit `.agents/` or this generated file unless explicitly instructed.

Private source context lives outside this code repo.
```

This reveals minimal information and keeps details in local generated files.

For client mode, it can say even less:

```markdown
# Local Agent Instructions

Use local `.agents/index.md` for workspace guidance.

Do not commit local agent context.
```

---

# Local Coordination Without Client Repo Pollution

Agents may not share memory, but they can share git-backed private state outside the code repo.

Use a state pack.

```text
workspace-state-pack/
  acme-site/
    handoffs/
      current-state.md
      active-threads/
    tasks/
      active/
      blocked/
      done/
    decisions-needed/
    risk-register.md
```

The binding points to this state location:

```toml
[[workspace]]
id = "acme-site"
path = "/home/jay/dev/acme-site"
state_pack = "shadowknight-state"
state_path = "clients/acme-site"
```

Generated output can include selected state files in `.agents/`, but source remains private.

---

# Handoffs

Handoffs are how team members and agents coordinate without shared memory.

Example:

```text
state-pack/acme-site/handoffs/current-state.md
```

```markdown
# Current State

## Last Updated

2026-05-11 by Jay using Codex

## Current Goal

Fix checkout flow issue.

## Completed

- Reproduced bug locally.
- Identified issue in payment callback route.

## In Progress

- Need to verify webhook signature handling.

## Blockers

- Need test Stripe webhook payload.

## Next Suggested Step

Create a failing test for the callback route.
```

Agents can update this private state pack, not the client repo.

---

# Tasks

Private task files can live in the state pack.

```text
state-pack/acme-site/tasks/active/fix-checkout.md
```

```markdown
---
id: task.fix-checkout
status: active
owner: jay
repo: acme-site
branch: fix-checkout-callback
---

# Fix Checkout Callback

## Goal

Fix checkout callback route.

## Acceptance Criteria

- Checkout succeeds with valid webhook.
- Invalid signatures are rejected.
- Tests cover callback validation.
```

Later this can sync with GitHub Issues/Linear/Jira, but file-based tasks work first.

---

# Decisions Needed

When an agent gets stuck, it should not guess.

It can write:

```text
state-pack/acme-site/decisions-needed/webhook-retry-policy.md
```

This lets the team review and decide.

---

# Skills-Only Use Case

The product must be useful even if someone only wants skills.

Simple flow:

```bash
npm install -g @shadowknight/team-agents
team-agents init
team-agents pack add core git@github.com:shadowknight/core-agent-pack.git
team-agents enable core.typescript-helper --global
team-agents enable core.git-helper --global
team-agents sync
```

Then in any repo:

```bash
team-agents sync
```

It generates selected skills locally.

No policies.
No wiki.
No team state.
No complexity required.

This is important for adoption.

---

# New User Experience

## Solo Developer

```bash
team-agents init
team-agents pack add core https://github.com/example/core-agent-pack.git
team-agents profile use web-dev --global
cd my-project
team-agents sync
```

Result:

```text
Local .agents/skills generated.
Project repo remains clean.
```

## Team Member

```bash
team-agents init
team-agents pack add shadowknight git@github.com:shadowknight/shadowknight-agent-pack.git
team-agents update
cd client-project
team-agents bind --profile client-work --profile web-dev
team-agents sync
```

Result:

```text
Private team context applied locally.
Client repo remains clean.
```

## Internal Product Repo

```bash
cd playfoursouls
team-agents bind --pack foursouls --profile internal-product
team-agents sync
```

Result:

```text
Internal product-specific context generated locally.
Optional pointer file can be committed if desired.
```

---

# Commands

## Setup

```bash
team-agents init
team-agents install
team-agents setup
```

`init` initializes user config.

`install` can mean install packs for current workspace.

`setup` can create a new pack or bind a repo, depending on context.

## Pack Management

```bash
team-agents pack add <id> <git-url>
team-agents pack remove <id>
team-agents pack list
team-agents pack update
team-agents pack create
```

## Binding

```bash
team-agents bind
team-agents bind --pack shadowknight --profile client-work
team-agents unbind
team-agents workspace list
team-agents workspace status
```

## Profiles

```bash
team-agents profile list
team-agents profile use web-dev --global
team-agents profile use client-work --workspace
```

## Sync

```bash
team-agents sync
team-agents sync --locked
team-agents sync --latest
team-agents sync --frozen
team-agents update
```

## Skills

```bash
team-agents skill list
team-agents skill enable core.typescript-helper --global
team-agents skill enable core.sql-helper --workspace
team-agents skill disable core.sql-helper --workspace
```

## Context

```bash
team-agents list
team-agents list skills
team-agents list policies
team-agents list playbooks
team-agents list contracts
team-agents list wiki
```

## Safety

```bash
team-agents protect
team-agents status
team-agents health
team-agents audit
```

## State

```bash
team-agents handoff
team-agents task new
team-agents decision-needed new
```

State commands should operate on private state packs, not the code repo, unless configured otherwise.

---

# Resolution Layers

Active context is resolved from:

```text
global personal defaults
+ global team defaults
+ workspace binding
+ selected profiles
+ project/client pack
+ explicit workspace enables/disables
+ local overrides
```

Recommended priority:

```text
workspace explicit override
> workspace explicit enable/disable
> project/client profile
> selected workspace profiles
> team defaults
> personal global defaults
> public/core defaults
```

Privacy policies can block lower layers.

Example:

```text
client privacy mode can block personal experimental skills
strict mode can block all scripts
public mode can block private packs
```

---

# Lockfiles

Need lockfiles, but not necessarily in the code repo.

## Global pack lock

```text
~/.team-agents/locks/packs.lock
```

Records pack source commits.

## Workspace lock

```text
~/.team-agents/workspaces/<workspace-id>/team-agents.lock
```

Records resolved context for that workspace.

For internal repos, the lockfile can optionally be committed.

For client repos, keep lockfile local unless approved.

---

# Local Workspace Folder

```text
~/.team-agents/workspaces/<workspace-id>/
  binding.toml
  team-agents.lock
  generated/
  state-cache/
  last-status.json
```

This is useful for privacy and reproducibility.

---

# Git Source Dependencies

Each pack can depend on other packs.

```toml
[[depends]]
id = "core"
url = "git@github.com:shadowknight/core-agent-pack.git"
ref = "main"
```

`team-agents pack update` should:

```text
1. Pull configured packs.
2. Read pack dependencies.
3. Pull dependencies recursively.
4. Detect cycles.
5. Build index.
6. Show changed items.
```

---

# Update Behavior

Separate pull from apply.

```bash
team-agents update
```

Pulls pack repos and dependencies.

```bash
team-agents sync
```

Regenerates local agent context.

```bash
team-agents sync --latest
```

Updates workspace lockfile to latest pack commits.

```bash
team-agents sync --locked
```

Regenerates from current lock only.

Default should be safe:

```text
Packs can update locally.
Workspace stays locked until explicitly updated, unless configured as floating.
```

For simpler users, allow floating mode:

```toml
[updates]
mode = "floating"
```

---

# Overrides

Overrides should be local/private.

```text
~/.team-agents/overrides/
~/.team-agents/workspaces/<id>/overrides/
```

Never put overrides in client repo by default.

Commands:

```bash
team-agents override core.typescript-helper
team-agents diff core.typescript-helper
team-agents reset core.typescript-helper
```

Warn if upstream changed after override base.

---

# Item Kinds

The system should support:

```text
skills
subagents
policies
workflows
playbooks
contracts
decisions
wiki
checklists
templates
handoffs
tasks
runbooks
```

For MVP:

```text
skills
policies
playbooks
checklists
wiki
```

Then add:

```text
contracts
decisions
handoffs
tasks
subagents
```

---

# Authority Order

Agents need to know which instructions win.

Recommended order:

```text
1. Current human request
2. Workspace privacy policy
3. Workspace policies
4. Workspace contracts
5. Playbooks/checklists
6. Decisions/ADRs
7. Skills
8. Wiki/background
9. Personal preferences
```

Skills should not override policies.

Wiki should not override contracts.

---

# Tool Compatibility

Canonical internal model:

```text
team-agents resolved context
```

Tool outputs:

```text
Codex:
  .agents/skills/
  AGENTS.md

Claude:
  .claude/skills/
  CLAUDE.md

Cursor:
  .cursor/rules/

Copilot:
  .github/copilot-instructions.md
```

MVP:

```text
Codex only:
  .agents/
  AGENTS.md
```

But design adapters from the beginning.

---

# Generated Context Index

Generate:

```text
.agents/index.md
```

Example:

```markdown
# Local Agent Context Index

Generated by team-agents.

This context was generated from private/local agent packs.
Do not commit this folder unless explicitly approved.

## Active Profiles

- client-work
- web-dev

## Required Reading

1. policies/agent-safety.md
2. policies/secrets-policy.md
3. checklists/end-of-task.md

## Skills

- skills/typescript-helper/
- skills/git-helper/

## Playbooks

- playbooks/add-feature.md
- playbooks/fix-bug.md
```

---

# Health Checks

`team-agents health` should detect:

```text
Generated .agents is tracked
Generated AGENTS.md is staged
Pack source missing
Pack dependency missing
Workspace binding path no longer exists
Lockfile drift
Override drift
Skills with scripts
Untrusted pack
Client mode with repo committed private files
Public mode with private pack enabled
```

This is critical for client work.

---

# Git Staging Protection

Command:

```bash
team-agents precommit
```

Could be used as a git hook.

Checks:

```text
Do not commit .agents/
Do not commit AGENTS.md if generated local
Do not commit .team-agents.local/
Do not commit private pack contents into client repo
```

Install hook:

```bash
team-agents hooks install
```

---

# Best MVP

The MVP should be simple enough for skills-only users but structured for teams.

## MVP 1: Universal Skill Pack Manager

Implement:

```text
team-agents init
team-agents pack add
team-agents pack update
team-agents skill list
team-agents skill enable --global
team-agents bind
team-agents sync
team-agents protect
team-agents status
```

Support:

```text
SKILL.md
private git packs
pack dependencies
profiles
workspace bindings
local generated .agents/skills
local git exclude protection
```

Do not yet implement:

```text
handoffs
tasks
contracts
subagents
complex governance
multi-tool adapters
```

## MVP 2: Team Context

Add:

```text
policies
playbooks
checklists
wiki
generated .agents/index.md
```

## MVP 3: Private Coordination State

Add:

```text
state packs
handoffs
tasks
decisions-needed
risk register
```

## MVP 4: Governance + Adapters

Add:

```text
Claude/Cursor/Copilot adapters
agent edit policies
audit
precommit hooks
roles
approvals
stale checks
```

---

# Suggested Implementation Structure

Use TypeScript.

Package:

```text
@shadowknight/team-agents
```

CLI:

```text
team-agents
```

Source layout:

```text
src/
  cli.ts

  commands/
    init.ts
    pack-add.ts
    pack-update.ts
    bind.ts
    sync.ts
    protect.ts
    status.ts
    health.ts
    skill-list.ts
    skill-enable.ts

  core/
    config.ts
    paths.ts
    pack-manager.ts
    dependency-resolver.ts
    workspace-manager.ts
    profile-resolver.ts
    item-indexer.ts
    lockfile.ts
    output-writer.ts
    git-protect.ts
    health-checker.ts

  models/
    pack.ts
    workspace.ts
    profile.ts
    item.ts
    lockfile.ts
    privacy.ts

  adapters/
    codex.ts
    claude.ts
    cursor.ts
    copilot.ts

  utils/
    git.ts
    fs.ts
    hash.ts
    toml.ts
    yaml.ts
```

---

# Codex Implementation Prompt

```text
Build a TypeScript CLI called `team-agents`.

This is a universal AI agent pack manager for personal and team use.

The key design is:
- Private git packs are the source of truth.
- Code repos should stay clean by default.
- Local workspace bindings decide which packs/profiles apply to which repo.
- Generated agent context is local-only by default.
- Skills are the MVP, but the architecture should support policies, playbooks, checklists, wiki, contracts, decisions, subagents, handoffs, and tasks later.

Implement MVP 1.

Commands:
- team-agents init
- team-agents pack add <id> <git-url>
- team-agents pack list
- team-agents pack update
- team-agents skill list
- team-agents skill enable <skill-id> --global
- team-agents skill disable <skill-id> --global
- team-agents bind
- team-agents bind --pack <id> --profile <profile> --privacy <mode>
- team-agents sync
- team-agents protect
- team-agents status
- team-agents health

Global files:
- ~/.team-agents/config.toml
- ~/.team-agents/bindings.toml
- ~/.team-agents/packs/<pack-id>/
- ~/.team-agents/workspaces/<workspace-id>/
- ~/.team-agents/locks/

Pack format:
- pack.toml
- profiles/*.toml
- skills/*/SKILL.md

pack.toml:
- id
- name
- version
- type
- depends[]

profiles:
- enabled.skills[]
- enabled.policies[] later
- enabled.playbooks[] later

Workspace binding:
- path
- packs[]
- profiles[]
- privacy mode
- generated output mode

MVP behavior:
1. `init`
   - creates ~/.team-agents folders and config.
2. `pack add`
   - clones a git repo into ~/.team-agents/packs/<id>.
3. `pack update`
   - pulls all packs.
   - reads pack.toml dependencies recursively.
   - clones/pulls dependencies.
   - detects cycles.
4. `skill list`
   - scans packs for skills/*/SKILL.md.
   - parses YAML frontmatter.
   - assigns IDs like <pack-id>.<skill-name>.
5. `skill enable --global`
   - stores global enabled skills in config.toml.
6. `bind`
   - creates or updates a local workspace binding for the current repo path.
   - stores it in ~/.team-agents/bindings.toml.
   - does not write private context into the repo.
7. `sync`
   - resolves global skills + workspace packs/profiles.
   - generates repo-local .agents/skills by default.
   - generates .agents/index.md.
   - generates AGENTS.md only if safe:
     - do not overwrite tracked AGENTS.md.
     - otherwise write a minimal router.
   - adds generated files to .git/info/exclude through `protect`.
   - never executes skill scripts.
8. `protect`
   - adds .agents/, AGENTS.md, AGENTS.local.md, and .team-agents.local/ to .git/info/exclude when safe.
   - do not exclude AGENTS.md if it is tracked.
9. `status`
   - shows active workspace, packs, profiles, enabled skills, generated output path, and warnings.
10. `health`
   - warns if generated files are tracked/staged, packs are missing, dependencies are missing, or skills contain scripts.

Privacy modes:
- personal
- internal
- client
- public
- strict

Default privacy mode:
- client

Important rules:
- Do not require a repo config file.
- Do not store private skills or policies in the code repo.
- Use .git/info/exclude instead of .gitignore for generated files.
- Support skills-only use cleanly.
- Design item kinds generically so policies/playbooks/wiki can be added later.
- Keep dotagents/SKILL.md compatibility where possible.
- Never auto-run scripts from a skill.

Add tests for:
- pack.toml parsing
- recursive dependency resolution
- SKILL.md discovery
- global skill enable/disable
- workspace binding
- sync output generation
- git exclude protection
- health warnings for tracked generated files
```

---

# Final Recommendation

Build this from the ground up as a **private pack overlay system**, not a repo-stored context system.

The best core product is:

```text
Install packs once.
Bind any repo to packs/profiles.
Generate local agent context.
Keep client repos clean.
Let teams share skills/workflows privately.
```

This preserves the skills-only use case while supporting the long-term team vision.

It also makes the tool valuable to anyone:

```text
Solo developer -> personal skill manager
Small team -> shared skill/workflow manager
Agency -> private client-safe agent context
Company -> standardized agent infrastructure
```
