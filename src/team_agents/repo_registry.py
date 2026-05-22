from __future__ import annotations

import tomllib
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.git_tools import find_git_root, list_normalized_remotes
from team_agents.toml_utils import read_toml, write_toml_document


def register_repo(
    corp_root: Path,
    workspace: Path,
    repo_id: str,
    repo_class: str,
    repo_group_id: str | None = None,
    enabled_skills: list[str] | None = None,
    optional_policies: list[str] | None = None,
    contexts: list[str] | None = None,
    recommended_agent_types: list[str] | None = None,
) -> Path:
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
    config_path.write_text(
        _render_repo_config(
            repo_id=repo_id,
            repo_class=repo_class,
            normalized_remotes=normalized_remotes,
            repo_group_id=repo_group_id,
            enabled_skills=enabled_skills,
            optional_policies=optional_policies,
            contexts=contexts,
            recommended_agent_types=recommended_agent_types,
        ),
        encoding="utf-8",
    )
    update_repo_index(corp_root / "indexes" / "repos.toml", repo_id, f"repos/{repo_id}")
    return config_path


def update_repo_config(
    config_path: Path,
    *,
    normalized_remotes: list[str] | None = None,
    repo_class: str | None = None,
    enabled_sources: list[str] | None = None,
    disabled_sources: list[str] | None = None,
    disabled_skills: list[str] | None = None,
    repo_group_id: str | None = None,
    enabled_skills: list[str] | None = None,
    optional_policies: list[str] | None = None,
    disabled_optional_policies: list[str] | None = None,
    contexts: list[str] | None = None,
    recommended_agent_types: list[str] | None = None,
) -> Path:
    data = read_toml(config_path)
    if normalized_remotes is not None:
        data["normalized_remotes"] = normalized_remotes
    if repo_class is not None:
        data["repo_class"] = repo_class
    if enabled_sources is not None:
        data["enabled_sources"] = enabled_sources
    if disabled_sources is not None:
        data["disabled_sources"] = disabled_sources
    if disabled_skills is not None:
        data["disabled_skills"] = disabled_skills
    if repo_group_id is not None:
        data["repo_group_id"] = repo_group_id
    if enabled_skills is not None:
        data["enabled_skills"] = enabled_skills
    if optional_policies is not None:
        data["optional_policies"] = optional_policies
    if disabled_optional_policies is not None:
        data["disabled_optional_policies"] = disabled_optional_policies
    if contexts is not None:
        data["contexts"] = contexts
    if recommended_agent_types is not None:
        data["recommended_agent_types"] = recommended_agent_types
    write_toml_document(config_path, data)
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


def _render_repo_config(
    repo_id: str,
    repo_class: str,
    normalized_remotes: list[str],
    repo_group_id: str | None = None,
    enabled_skills: list[str] | None = None,
    optional_policies: list[str] | None = None,
    contexts: list[str] | None = None,
    recommended_agent_types: list[str] | None = None,
) -> str:
    lines = [
        f'id = "{repo_id}"',
        "normalized_remotes = [",
    ]
    for remote in normalized_remotes:
        lines.append(f'  "{remote}",')
    lines.append("]")
    if repo_group_id is not None:
        lines.append(f'repo_group_id = "{repo_group_id}"')
    lines.append(f'repo_class = "{repo_class}"')
    if enabled_skills:
        lines.append(_render_string_list("enabled_skills", enabled_skills))
    if optional_policies:
        lines.append(_render_string_list("optional_policies", optional_policies))
    if contexts:
        lines.append(_render_string_list("contexts", contexts))
    if recommended_agent_types:
        lines.append(_render_string_list("recommended_agent_types", recommended_agent_types))
    lines.append("")
    return "\n".join(lines)


def _render_string_list(key: str, values: list[str]) -> str:
    rendered = ", ".join(f'"{value}"' for value in values)
    return f"{key} = [{rendered}]"
