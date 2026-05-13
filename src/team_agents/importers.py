from __future__ import annotations

from pathlib import Path

from team_agents.toml_utils import read_toml, write_toml_document, write_simple_toml


TEXT_RESOURCE_EXTENSIONS = {".md", ".txt", ".yaml", ".yml", ".json"}


def import_folder_skills(
    source_root: Path,
    layer_root: Path,
    source_type: str,
    namespace: str,
    include_system: bool = False,
    privacy: str = "repo-safe",
) -> dict[str, int]:
    source_root = source_root.resolve()
    layer_root = layer_root.resolve()
    skills_root = layer_root / "skills"
    docs_root = layer_root / "docs"
    imported_skills = 0
    imported_docs = 0

    enabled_skills: list[str] = []
    config_path = layer_root / "config.toml"
    existing = read_toml(config_path)
    existing_enabled = _str_list(existing.get("enabled_skills"))

    for skill_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        if skill_dir.name == ".system" and not include_system:
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        slug = _sanitize_slug(skill_dir.name)
        skill_id = f"{source_type}.{namespace}.skill.{slug}"
        imported_skills += 1
        enabled_skills.append(skill_id)
        target = skills_root / slug
        target.mkdir(parents=True, exist_ok=True)
        write_simple_toml(
            target / "item.toml",
            {
                "id": skill_id,
                "kind": "skill",
                "title": skill_dir.name,
                "privacy": privacy,
                "source_note": f"Imported from {skill_dir}",
            },
        )
        body = skill_md.read_text(encoding="utf-8")
        resource_docs = []
        for resource in sorted(
            path
            for path in skill_dir.rglob("*")
            if path.is_file() and path.name != "SKILL.md" and path.suffix.lower() in TEXT_RESOURCE_EXTENSIONS
        ):
            relative = resource.relative_to(skill_dir)
            doc_slug = _sanitize_slug(f"{slug}-{relative.as_posix().replace('/', '-')}")
            doc_id = f"{source_type}.{namespace}.doc.{doc_slug}"
            imported_docs += 1
            resource_docs.append((doc_id, relative))
            doc_dir = docs_root / doc_slug
            doc_dir.mkdir(parents=True, exist_ok=True)
            write_simple_toml(
                doc_dir / "item.toml",
                {
                    "id": doc_id,
                    "kind": "doc",
                    "title": f"{skill_dir.name} resource {relative.as_posix()}",
                    "privacy": privacy,
                    "source_note": f"Imported from {resource}",
                },
            )
            header = f"# {skill_dir.name} resource\n\nSource: `{relative.as_posix()}`\n\n"
            doc_dir.joinpath("body.md").write_text(header + resource.read_text(encoding="utf-8"), encoding="utf-8")
        if resource_docs:
            body += "\n\n## Imported Resources\n"
            for doc_id, relative in resource_docs:
                body += f"- `{doc_id}` from `{relative.as_posix()}`\n"
        target.joinpath("body.md").write_text(body, encoding="utf-8")

    existing["enabled_skills"] = sorted(set(existing_enabled).union(enabled_skills))
    _ensure_layer_defaults(existing)
    write_toml_document(config_path, existing)
    for name in ["policies", "sources", "workspaces"]:
        (layer_root / name).mkdir(parents=True, exist_ok=True)
    return {"skills": imported_skills, "docs": imported_docs}


def import_codex_skills(
    source_root: Path,
    layer_root: Path,
    source_type: str,
    namespace: str,
    include_system: bool = False,
    privacy: str = "repo-safe",
) -> dict[str, int]:
    return import_folder_skills(
        source_root=source_root,
        layer_root=layer_root,
        source_type=source_type,
        namespace=namespace,
        include_system=include_system,
        privacy=privacy,
    )


def _ensure_layer_defaults(data: dict[str, object]) -> None:
    data.setdefault("enabled_sources", [])
    data.setdefault("disabled_sources", [])
    data.setdefault("enabled_skills", [])
    data.setdefault("disabled_skills", [])
    if "baseline_policies" in data:
        data.setdefault("protected_fields", [])
    else:
        data.setdefault("optional_policies", [])
        data.setdefault("disabled_optional_policies", [])
        data.setdefault("preferred_agent_types", [])
    data.setdefault("docs", [])
    data.setdefault("disabled_docs", [])


def _sanitize_slug(value: str) -> str:
    slug = []
    for char in value.lower():
        if char.isalnum() or char in {"-", "_"}:
            slug.append(char)
        else:
            slug.append("-")
    result = "".join(slug).strip("-")
    while "--" in result:
        result = result.replace("--", "-")
    return result or "item"


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
