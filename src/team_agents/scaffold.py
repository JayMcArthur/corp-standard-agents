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

        ## First Run

        1. Install the product:
           - `bash scripts/install.sh`
        2. Point `team-agents` at this control repo:
           - `team-agents setup --corp-repo /path/to/this-repo --user <username>`
        3. Clone or open a repo and attach it:
           - `team-agents attach`
        4. If you own the repo or shared defaults, shape them with:
           - `team-agents configure-repo`
           - `team-agents configure-group`

        ## Starter Model

        This scaffold includes:

        - an org baseline skill for steady-state work
        - an unknown-workspace onboarding skill for first-time repo intake
        - one starter repo-group (`platform`)
        - one starter repo entry (`internal-app`) linked to that group

        Layout:

        - `org/`: org-wide defaults, starter skills, policies, and docs
        - `repo-groups/`: shared overlays for groups of repos
        - `repos/`: per-repo overrides
        - `users/`: corp-resident user profiles under `users/<username>/`
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
        dest / "org" / "docs" / "authoring-example" / "item.toml",
        """
        # Doc items use the same schema as skills and policies.
        id = "corp.example-org.doc.authoring-example"
        kind = "doc"
        title = "Authoring Example"
        privacy = "repo-safe"
        """,
    )
    _write(
        dest / "org" / "docs" / "authoring-example" / "body.md",
        """
        # Authoring Example

        Replace this with corp-specific reference material that should resolve into workspaces.
        """,
    )
    _write(
        dest / "indexes" / "repo-groups.toml",
        """
        [[repo_group]]
        id = "platform"
        path = "repo-groups/platform"
        """,
    )
    _write(
        dest / "indexes" / "repos.toml",
        """
        [[repo]]
        id = "internal-app"
        path = "repos/internal-app"
        """,
    )
    _write(dest / "indexes" / "sources.toml", "")
    _write(
        dest / "repo-groups" / "platform" / "config.toml",
        """
        id = "platform"
        enabled_skills = ["corp.example-org.skill.recursive-planning"]
        docs = ["corp.example-org.doc.platform-map"]
        """,
    )
    _write(
        dest / "repo-groups" / "platform" / "docs" / "platform-map" / "item.toml",
        """
        id = "corp.example-org.doc.platform-map"
        kind = "doc"
        title = "Platform Map"
        privacy = "repo-safe"
        """,
    )
    _write(
        dest / "repo-groups" / "platform" / "docs" / "platform-map" / "body.md",
        """
        # Platform Map

        Replace this with the shared conventions, boundaries, and deployment notes that sister repos in this group should inherit.
        """,
    )
    _write(
        dest / "repos" / "internal-app" / "config.toml",
        """
        id = "internal-app"
        normalized_remotes = ["git.example.test/example/internal-app"]
        repo_group_id = "platform"
        repo_class = "internal"
        enabled_skills = []
        """,
    )
    _write(
        dest / "users" / "README.md",
        """
        # User Profiles

        Each developer gets a corp-resident profile at `users/<username>/`.

        A profile contains:

        - `config.toml` for user-level activations and workspace bindings
        - `skills/`, `policies/`, `docs/`, and `sources/` for user-owned items

        `team-agents setup --corp-repo <path> --user <username>` will create the user folder if it does not exist yet.
        """,
    )


def init_user_overrides(dest: Path) -> None:
    dest = dest.resolve()
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
        docs = []
        disabled_docs = []
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
    for name in ["policies", "docs", "sources", "workspaces"]:
        (dest / name).mkdir(parents=True, exist_ok=True)


def init_user_profile(dest: Path, username: str) -> None:
    dest = dest.resolve()
    _write(
        dest / "config.toml",
        f"""
        id = "{username}"
        enabled_sources = []
        disabled_sources = []
        enabled_skills = ["user.{username}.skill.personal-shell"]
        disabled_skills = []
        optional_policies = []
        disabled_optional_policies = []
        docs = []
        disabled_docs = []
        preferred_agent_types = ["local-helper"]
        """,
    )
    _write(
        dest / "skills" / "personal-shell" / "item.toml",
        f"""
        id = "user.{username}.skill.personal-shell"
        kind = "skill"
        title = "Personal Shell"
        privacy = "repo-safe"
        """,
    )
    _write(
        dest / "skills" / "personal-shell" / "body.md",
        """
        ## Personal Shell

        Replace this with your user-specific shell helper skill.
        """,
    )
    for name in ["skills", "policies", "docs", "sources", "workspaces"]:
        (dest / name).mkdir(parents=True, exist_ok=True)
