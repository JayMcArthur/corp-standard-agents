from __future__ import annotations

import tomllib
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.git_tools import find_git_root, list_normalized_remotes


def register_repo(corp_root: Path, workspace: Path, repo_id: str, repo_class: str) -> Path:
    corp_root = corp_root.resolve()
    workspace = workspace.resolve()
    git_root = find_git_root(workspace)
    if git_root is None:
        raise ValidationError(f"Workspace is not inside a git repo: {workspace}")
    normalized_remotes = list_normalized_remotes(git_root)
    if not normalized_remotes:
        raise ValidationError(f"Workspace git repo has no remotes: {git_root}")

    repo_dir = corp_root / "repos" / repo_id
    if repo_dir.exists():
        raise ValidationError(f"Repo mapping already exists: {repo_dir}")
    repo_dir.mkdir(parents=True, exist_ok=False)
    config_path = repo_dir / "config.toml"
    config_path.write_text(_render_repo_config(repo_id, repo_class, normalized_remotes), encoding="utf-8")
    update_repo_index(corp_root / "indexes" / "repos.toml", repo_id, f"repos/{repo_id}")
    return config_path


def update_repo_index(index_path: Path, repo_id: str, repo_path: str) -> None:
    existing = []
    if index_path.exists() and index_path.read_text(encoding="utf-8").strip():
        data = tomllib.loads(index_path.read_text(encoding="utf-8"))
        existing = data.get("repo", [])
    if any(entry.get("id") == repo_id for entry in existing):
        raise ValidationError(f"Repo index already contains id {repo_id}")
    existing.append({"id": repo_id, "path": repo_path})
    existing.sort(key=lambda entry: str(entry["id"]))
    lines: list[str] = []
    for entry in existing:
        lines.extend(
            [
                "[[repo]]",
                f'id = "{entry["id"]}"',
                f'path = "{entry["path"]}"',
                "",
            ]
        )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _render_repo_config(repo_id: str, repo_class: str, normalized_remotes: list[str]) -> str:
    lines = [
        f'id = "{repo_id}"',
        "normalized_remotes = [",
    ]
    for remote in normalized_remotes:
        lines.append(f'  "{remote}",')
    lines.extend(
        [
            "]",
            f'repo_class = "{repo_class}"',
            'enabled_skills = ["corp.example-org.skill.shell-global"]',
            "",
        ]
    )
    return "\n".join(lines)
