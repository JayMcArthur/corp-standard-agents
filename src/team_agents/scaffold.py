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
        minimal_enabled_skills = ["corp.example-org.skill.recursive-planning"]
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
        enabled_skills = []
        disabled_skills = []
        optional_policies = []
        disabled_optional_policies = []
        docs = []
        disabled_docs = []
        preferred_agent_types = []
        """,
    )
    for name in ["skills", "policies", "docs", "sources", "workspaces"]:
        (dest / name).mkdir(parents=True, exist_ok=True)
