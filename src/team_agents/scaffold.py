from __future__ import annotations

from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def init_corp_repo(dest: Path) -> None:
    dest = dest.resolve()
    _write(
        dest / "org" / "config.toml",
        """
        id = "example-org"
        enabled_sources = []
        enabled_skills = ["corp.example-org.skill.shell-global"]
        baseline_policies = ["corp.example-org.policy.no-leaks"]
        recommended_agent_types = ["shell"]
        minimal_enabled_skills = ["corp.example-org.skill.shell-global"]
        protected_fields = ["baseline_policies", "privacy_rules"]
        """,
    )
    _write(
        dest / "org" / "skills" / "shell-global" / "item.toml",
        """
        id = "corp.example-org.skill.shell-global"
        kind = "skill"
        title = "Shell Global"
        privacy = "repo-safe"
        """,
    )
    _write(dest / "org" / "skills" / "shell-global" / "body.md", "Replace this with your global shell helper skill.")
    _write(
        dest / "org" / "policies" / "no-leaks" / "item.toml",
        """
        id = "corp.example-org.policy.no-leaks"
        kind = "policy"
        title = "No Leaks"
        privacy = "repo-safe"
        """,
    )
    _write(dest / "org" / "policies" / "no-leaks" / "body.md", "Generated corp-private context must never be committed to client repos.")
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
        normalized_remotes = ["github.com/example/example-repo"]
        repo_class = "internal"
        enabled_skills = ["corp.example-org.skill.shell-global"]
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
    _write(dest / "skills" / "personal-shell" / "body.md", "Replace this with your personal shell helper skill.")
    for name in ["policies", "docs", "sources", "workspaces"]:
        (dest / name).mkdir(parents=True, exist_ok=True)
