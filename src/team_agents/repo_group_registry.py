from __future__ import annotations

import tomllib
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.toml_utils import read_toml, write_toml_document


def register_repo_group(
    corp_root: Path,
    group_id: str,
    *,
    enabled_skills: list[str] | None = None,
    disabled_skills: list[str] | None = None,
    enabled_sources: list[str] | None = None,
    disabled_sources: list[str] | None = None,
    optional_policies: list[str] | None = None,
    disabled_optional_policies: list[str] | None = None,
    docs: list[str] | None = None,
    recommended_agent_types: list[str] | None = None,
) -> Path:
    corp_root = corp_root.resolve()
    group_dir = corp_root / "repo-groups" / group_id
    if group_dir.exists():
        raise ValidationError(f"Repo-group mapping already exists: {group_dir}")
    group_dir.mkdir(parents=True, exist_ok=False)
    config_path = group_dir / "config.toml"
    write_toml_document(
        config_path,
        _repo_group_config_payload(
            group_id=group_id,
            enabled_skills=enabled_skills,
            disabled_skills=disabled_skills,
            enabled_sources=enabled_sources,
            disabled_sources=disabled_sources,
            optional_policies=optional_policies,
            disabled_optional_policies=disabled_optional_policies,
            docs=docs,
            recommended_agent_types=recommended_agent_types,
        ),
    )
    update_repo_group_index(corp_root / "indexes" / "repo-groups.toml", group_id, f"repo-groups/{group_id}")
    return config_path


def update_repo_group_config(
    config_path: Path,
    *,
    enabled_skills: list[str] | None = None,
    disabled_skills: list[str] | None = None,
    enabled_sources: list[str] | None = None,
    disabled_sources: list[str] | None = None,
    optional_policies: list[str] | None = None,
    disabled_optional_policies: list[str] | None = None,
    docs: list[str] | None = None,
    recommended_agent_types: list[str] | None = None,
) -> Path:
    data = read_toml(config_path)
    if enabled_skills is not None:
        data["enabled_skills"] = enabled_skills
    if disabled_skills is not None:
        data["disabled_skills"] = disabled_skills
    if enabled_sources is not None:
        data["enabled_sources"] = enabled_sources
    if disabled_sources is not None:
        data["disabled_sources"] = disabled_sources
    if optional_policies is not None:
        data["optional_policies"] = optional_policies
    if disabled_optional_policies is not None:
        data["disabled_optional_policies"] = disabled_optional_policies
    if docs is not None:
        data["docs"] = docs
    if recommended_agent_types is not None:
        data["recommended_agent_types"] = recommended_agent_types
    write_toml_document(config_path, data)
    return config_path


def update_repo_group_index(index_path: Path, group_id: str, group_path: str) -> None:
    existing = []
    if index_path.exists() and index_path.read_text(encoding="utf-8").strip():
        data = tomllib.loads(index_path.read_text(encoding="utf-8"))
        existing = data.get("repo_group", [])
    if any(entry.get("id") == group_id for entry in existing):
        raise ValidationError(f"Repo-group index already contains id {group_id}")
    existing.append({"id": group_id, "path": group_path})
    existing.sort(key=lambda entry: str(entry["id"]))
    lines: list[str] = []
    for entry in existing:
        lines.extend(
            [
                "[[repo_group]]",
                f'id = "{entry["id"]}"',
                f'path = "{entry["path"]}"',
                "",
            ]
        )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _repo_group_config_payload(
    *,
    group_id: str,
    enabled_skills: list[str] | None,
    disabled_skills: list[str] | None,
    enabled_sources: list[str] | None,
    disabled_sources: list[str] | None,
    optional_policies: list[str] | None,
    disabled_optional_policies: list[str] | None,
    docs: list[str] | None,
    recommended_agent_types: list[str] | None,
) -> dict[str, object]:
    payload: dict[str, object] = {"id": group_id}
    if enabled_skills:
        payload["enabled_skills"] = enabled_skills
    if disabled_skills:
        payload["disabled_skills"] = disabled_skills
    if enabled_sources:
        payload["enabled_sources"] = enabled_sources
    if disabled_sources:
        payload["disabled_sources"] = disabled_sources
    if optional_policies:
        payload["optional_policies"] = optional_policies
    if disabled_optional_policies:
        payload["disabled_optional_policies"] = disabled_optional_policies
    if docs:
        payload["docs"] = docs
    if recommended_agent_types:
        payload["recommended_agent_types"] = recommended_agent_types
    return payload
