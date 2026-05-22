from __future__ import annotations

from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def init_corp_repo(dest: Path) -> None:
    dest = dest.resolve()
    _write(
        dest / "README.md",
        """
        # Corp Control Repo

        This repo is the source of truth for corp-wide team-agents configuration.

        Layout:

        - `org/`: org-wide defaults, starter contexts, policies, completion gates, skills, playbooks, packs, and profiles
        - `repo-groups/`: shared standards for groups of repos
        - `repos/`: per-repo standards and activation
        - `users/`: optional corp-managed user profiles under `users/<username>/`
        - `indexes/`: registry files for repos, repo-groups, and sources

        Each item directory uses `item.toml` for metadata and `body.md` for content.
        """,
    )
    _write(
        dest / "org" / "config.toml",
        """
        id = "example-org"
        enabled_sources = []
        enabled_skills = ["corp.example-org.skill.recursive-planning"]
        baseline_policies = ["corp.example-org.policy.no-leaks"]
        required_completion_gates = ["corp.example-org.completion_gate.definition-of-done"]
        allowed_profiles = ["coder", "reviewer"]
        default_profile = "coder"
        recommended_agent_types = ["shell"]
        minimal_enabled_skills = ["corp.example-org.skill.repo-onboarding"]
        protected_fields = ["baseline_policies", "privacy_rules"]
        """,
    )
    _write(
        dest / "org" / "skills" / "recursive-planning" / "item.toml",
        """
        # Required fields for every item.
        id = "corp.example-org.skill.recursive-planning"
        kind = "skill"
        title = "Recursive Planning"
        privacy = "repo-safe"
        owner = "agent-platform"
        maintainer = "agent-platform"
        status = "active"
        review_status = "approved"
        """,
    )
    _write(
        dest / "org" / "skills" / "recursive-planning" / "body.md",
        """
        ## Recursive Planning

        Use this as a realistic starter skill for broad, uncertain, multi-step work.
        """,
    )
    _write(
        dest / "org" / "skills" / "repo-onboarding" / "item.toml",
        """
        id = "corp.example-org.skill.repo-onboarding"
        kind = "skill"
        title = "Repo Onboarding"
        privacy = "repo-safe"
        usage_mode = "one-time"
        recommended_agent_types = ["shell"]
        """,
    )
    _write(
        dest / "org" / "skills" / "repo-onboarding" / "body.md",
        """
        ## Repo Onboarding

        Use this when you first land in an unknown repo or folder.

        Goal:
        - figure out whether this location should attach to an existing repo
        - figure out whether it should attach to a shared repo-group
        - or configure it as a new repo if you own it

        Normal path:
        - run `team-agents attach`
        - if you are the repo owner, continue with `team-agents configure-repo`
        - if multiple sister repos should share defaults, continue with `team-agents configure-group`
        """,
    )
    _write(
        dest / "org" / "policies" / "no-leaks" / "item.toml",
        """
        # Policy items may optionally declare structured `policy_rules`.
        id = "corp.example-org.policy.no-leaks"
        kind = "policy"
        title = "No Leaks"
        privacy = "repo-safe"
        """,
    )
    _write(dest / "org" / "policies" / "no-leaks" / "body.md", "Generated corp-private context must never be committed to client repos.")
    _write(
        dest / "org" / "completion_gates" / "definition-of-done" / "item.toml",
        """
        id = "corp.example-org.completion_gate.definition-of-done"
        kind = "completion_gate"
        title = "Definition Of Done"
        privacy = "repo-safe"
        evidence_required = [
          "tests_run",
          "files_changed_summary",
          "risk_notes",
          "verification_command_output"
        ]
        """,
    )
    _write(
        dest / "org" / "completion_gates" / "definition-of-done" / "body.md",
        """
        # Definition Of Done

        Work is not complete until generated context has been checked, required tests have run, and user-visible changes are summarized.
        """,
    )
    _write(
        dest / "org" / "contexts" / "authoring-example" / "item.toml",
        """
        # Context items use the same schema as skills and policies.
        id = "corp.example-org.context.authoring-example"
        kind = "context"
        title = "Authoring Example"
        privacy = "repo-safe"
        """,
    )
    _write(
        dest / "org" / "contexts" / "authoring-example" / "body.md",
        """
        # Authoring Example

        Replace this with corp-specific reference material that should resolve into workspaces.
        """,
    )
    _write(
        dest / "org" / "playbooks" / "coder-loop" / "item.toml",
        """
        id = "corp.example-org.playbook.coder-loop"
        kind = "playbook"
        title = "Coder Loop"
        privacy = "repo-safe"
        inputs = ["task_request", "repo_context"]
        outputs = ["patch", "verification_summary"]
        evidence_required = ["tests_run", "files_changed_summary"]
        stop_conditions = ["ambiguous_requirement", "security_boundary_unclear"]
        """,
    )
    _write(
        dest / "org" / "playbooks" / "coder-loop" / "body.md",
        """
        # Coder Loop

        Plan the smallest useful change, implement it, run focused verification, then summarize the result.
        """,
    )
    _write(
        dest / "org" / "playbooks" / "pr-review" / "item.toml",
        """
        id = "corp.example-org.playbook.pr-review"
        kind = "playbook"
        title = "PR Review"
        privacy = "repo-safe"
        inputs = ["diff", "repo_context"]
        outputs = ["review_findings", "risk_notes"]
        evidence_required = ["findings_with_file_refs", "verification_notes"]
        stop_conditions = ["insufficient_context", "unsafe_change"]
        """,
    )
    _write(
        dest / "org" / "playbooks" / "pr-review" / "body.md",
        """
        # PR Review

        Review behavior, risk, tests, and generated context provenance before approval.
        """,
    )
    _write(
        dest / "org" / "playbooks" / "prep-before-code" / "item.toml",
        """
        id = "corp.example-org.playbook.prep-before-code"
        kind = "playbook"
        title = "Prep Before Code"
        privacy = "repo-safe"
        tags = ["prep", "mise-en-place", "large-task"]
        inputs = ["task_request", "repo_context"]
        outputs = ["implementation_plan", "verification_plan"]
        evidence_required = ["scope_notes", "risk_notes", "verification_plan"]
        stop_conditions = ["ambiguous_requirement", "security_boundary_unclear", "missing_acceptance_criteria"]
        """,
    )
    _write(
        dest / "org" / "playbooks" / "prep-before-code" / "body.md",
        """
        # Prep Before Code

        Use this before implementation when work is broad, ambiguous, risky, or likely to span multiple files.

        ## Phases

        1. Context grounding
        2. Collaborative specification
        3. Task decomposition
        4. Acceptance criteria
        5. Verification plan
        6. Risk notes

        ## Prep artifacts

        Capture the agreed scope, task breakdown, acceptance criteria, verification plan, and risk notes before coding.
        """,
    )
    _write(
        dest / "org" / "completion_gates" / "prep-artifacts" / "item.toml",
        """
        id = "corp.example-org.completion_gate.prep-artifacts"
        kind = "completion_gate"
        title = "Prep Artifacts"
        privacy = "repo-safe"
        evidence_required = [
          "context_grounding",
          "task_decomposition",
          "acceptance_criteria",
          "verification_plan",
          "risk_notes"
        ]
        """,
    )
    _write(
        dest / "org" / "completion_gates" / "prep-artifacts" / "body.md",
        """
        # Prep Artifacts

        For large tasks, show context grounding, task decomposition, acceptance criteria, verification plan, and risk notes before implementation is considered ready.
        """,
    )
    _write(
        dest / "org" / "packs" / "corp-baseline" / "item.toml",
        """
        id = "corp.example-org.pack.corp-baseline"
        kind = "pack"
        title = "Corp Baseline"
        privacy = "repo-safe"
        owner = "agent-platform"
        maintainer = "agent-platform"
        status = "active"
        review_status = "approved"
        stop_conditions = ["secrets_detected", "tests_fail_after_two_attempts", "unclear_requirement"]

        [activation]
        required = [
          "corp.example-org.policy.no-leaks",
          "corp.example-org.completion_gate.definition-of-done"
        ]
        enabled = [
          "corp.example-org.context.authoring-example",
          "corp.example-org.skill.recursive-planning"
        ]
        """,
    )
    _write(
        dest / "org" / "packs" / "corp-baseline" / "body.md",
        """
        # Corp Baseline

        Starter bundle for baseline corporate context.
        """,
    )
    _write(
        dest / "org" / "packs" / "preparation" / "item.toml",
        """
        id = "corp.example-org.pack.preparation"
        kind = "pack"
        title = "Preparation"
        privacy = "repo-safe"

        [activation]
        required = ["corp.example-org.completion_gate.prep-artifacts"]
        enabled = ["corp.example-org.playbook.prep-before-code"]
        """,
    )
    _write(
        dest / "org" / "packs" / "preparation" / "body.md",
        """
        # Preparation

        Mise-en-place pack for complex implementation work.
        """,
    )
    _write(
        dest / "org" / "profiles" / "coder.toml",
        """
        id = "coder"
        title = "Coder"
        owner = "agent-platform"
        maintainer = "agent-platform"
        status = "active"
        review_status = "approved"
        stop_conditions = ["secrets_detected", "unclear_requirement"]

        [activation]
        enabled = [
          "corp.example-org.pack.corp-baseline",
          "corp.example-org.pack.preparation",
          "corp.example-org.playbook.coder-loop"
        ]
        """,
    )
    _write(
        dest / "org" / "profiles" / "reviewer.toml",
        """
        id = "reviewer"
        title = "Reviewer"
        owner = "agent-platform"
        maintainer = "agent-platform"
        status = "active"
        review_status = "approved"

        [activation]
        required = ["corp.example-org.completion_gate.definition-of-done"]
        enabled = [
          "corp.example-org.pack.corp-baseline",
          "corp.example-org.pack.preparation",
          "corp.example-org.playbook.pr-review"
        ]
        """,
    )
    _write(
        dest / "indexes" / "repos.toml",
        """
        [[repo]]
        id = "example-repo"
        path = "repos/example-repo"
        """,
    )
    _write(dest / "indexes" / "repo-groups.toml", "")
    _write(dest / "indexes" / "sources.toml", "")
    _write(
        dest / "repos" / "example-repo" / "config.toml",
        """
        id = "example-repo"
        normalized_remotes = ["git.example.test/example/example-repo"]
        repo_class = "internal"
        enabled_skills = ["corp.example-org.skill.recursive-planning"]
        required_completion_gates = ["corp.example-org.completion_gate.repo-bootstrap"]
        """,
    )
    _write(
        dest / "repos" / "example-repo" / "completion_gates" / "repo-bootstrap" / "item.toml",
        """
        id = "corp.example-org.completion_gate.repo-bootstrap"
        kind = "completion_gate"
        title = "Repo Bootstrap"
        privacy = "repo-safe"
        tags = ["bootstrap", "minimal-verification"]
        """,
    )
    _write(
        dest / "repos" / "example-repo" / "completion_gates" / "repo-bootstrap" / "body.md",
        """
        # Repo Bootstrap

        Last verified: 2026-05-21

        ## Environment prerequisites

        - Python 3.12+
        - Git

        ## Commands

        ```bash
        python -m venv .venv
        . .venv/bin/activate
        python -m pip install -e .
        python -m unittest discover -s tests -v
        ```

        ## Minimal verification

        ```bash
        PYTHONPATH=src python -m unittest discover -s tests -v
        ```

        ## Common setup failures

        - Missing Python 3.12: install a compatible Python before running tests.
        - Editable install fails: upgrade pip, then retry `python -m pip install -e .`.

        ## Verification evidence

        Fresh scaffold example, verified by the generated minimal test command above.
        """,
    )
    _write(
        dest / "users" / "README.md",
        """
        # Corp-Managed User Profiles

        Local user layers are the default user model and are configured with:

        ```bash
        team-agents setup --corp-repo <path> --user-path ~/team-agents-user
        ```

        This folder is only for companies that explicitly want corp-managed user profiles:

        - `config.toml` for user-level activations and workspace bindings
        - `contexts/`, `policies/`, `completion_gates/`, `skills/`, `playbooks/`, `packs/`, `profiles/`, and `sources/`

        `team-agents setup --corp-repo <path> --user <username>` creates this explicit corp-managed folder if it does not exist yet.
        """,
    )


def init_user_layer(dest: Path) -> None:
    dest = dest.resolve()
    _write(
        dest / "README.md",
        """
        # Local User Layer

        This folder stores personal team-agents context and workspace bindings for this machine.

        Local user layers may add personal contexts, policies, completion gates, skills, playbooks, packs, profiles, and sources. They must not weaken required corp, repo, or profile standards.

        Daily workspace playbook:

        ```bash
        team-agents attach --workspace /path/to/workspace
        team-agents context --workspace /path/to/workspace --pretty
        team-agents sync --workspace /path/to/workspace
        ```

        Personal overrides belong in `config.toml`. Use them to tune optional context, not to weaken required standards:

        ```toml
        disabled_skills = ["corp.example-org.skill.noisy-helper"]

        [[item_override]]
        id = "corp.example-org.skill.some-helper"
        timeout_seconds = 20
        source_note = "Personal timeout override for this machine"
        ```
        """,
    )
    _write(
        dest / "config.toml",
        """
        id = "local"
        enabled_sources = []
        disabled_sources = []
        enabled_skills = ["user.local.skill.personal-shell"]
        disabled_skills = []
        optional_policies = []
        disabled_optional_policies = []
        contexts = []
        disabled_contexts = []
        preferred_agent_types = ["local-helper"]
        """,
    )
    _write(
        dest / "skills" / "personal-shell" / "item.toml",
        """
        id = "user.local.skill.personal-shell"
        kind = "skill"
        title = "Personal Shell"
        privacy = "repo-safe"
        """,
    )
    _write(
        dest / "skills" / "personal-shell" / "body.md",
        """
        ## Personal Shell

        Replace this with your personal shell helper skill.
        """,
    )
    for name in ["policies", "contexts", "completion_gates", "playbooks", "packs", "profiles", "activations", "sources", "workspaces"]:
        (dest / name).mkdir(parents=True, exist_ok=True)


def init_user_profile(dest: Path, username: str) -> None:
    dest = dest.resolve()
    _write(
        dest / "config.toml",
        f"""
        id = "{username}"
        enabled_sources = []
        disabled_sources = []
        enabled_skills = []
        disabled_skills = []
        optional_policies = []
        disabled_optional_policies = []
        contexts = []
        disabled_contexts = []
        preferred_agent_types = []
        """,
    )
    for name in ["skills", "policies", "contexts", "completion_gates", "playbooks", "packs", "profiles", "activations", "sources", "workspaces"]:
        (dest / name).mkdir(parents=True, exist_ok=True)
