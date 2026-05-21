from __future__ import annotations

import shutil
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.toml_utils import read_toml, write_toml_document
from team_agents.validation import validate_canonical_id


PROMOTION_CHECKLIST_FIELDS = {
    "task",
    "applicability",
    "evidence",
    "risks",
    "scope",
    "redundancy",
}


def promote_skills(
    corp_root: Path,
    user_root: Path,
    from_layer: str,
    to_layer: str,
    skill_ids: list[str],
    from_repo_id: str | None = None,
    to_repo_id: str | None = None,
    all_imported: bool = False,
) -> list[str]:
    source_root, source_type, source_namespace = resolve_layer_target(corp_root, user_root, from_layer, from_repo_id)
    dest_root, dest_type, dest_namespace = resolve_layer_target(corp_root, user_root, to_layer, to_repo_id)
    if source_root.resolve() == dest_root.resolve():
        raise ValidationError("Source and destination layers must differ")

    selected_ids = resolve_selected_skill_ids(source_root, skill_ids, all_imported)
    promoted: list[str] = []
    source_config = read_toml(source_root / "config.toml")
    dest_config = read_toml(dest_root / "config.toml")
    source_enabled = [str(item) for item in source_config.get("enabled_skills", [])]
    dest_enabled = [str(item) for item in dest_config.get("enabled_skills", [])]
    source_disabled = [str(item) for item in source_config.get("disabled_skills", [])]
    dest_disabled = [str(item) for item in dest_config.get("disabled_skills", [])]

    for old_skill_id in selected_ids:
        _, _, _, slug = validate_canonical_id(old_skill_id, expected_kind="skill", path=source_root / "config.toml")
        skill_dir = source_root / "skills" / slug
        if not skill_dir.exists():
            raise ValidationError(f"Skill path does not exist for {old_skill_id}: {skill_dir}")
        new_skill_id = f"{dest_type}.{dest_namespace}.skill.{slug}"
        dest_skill_dir = dest_root / "skills" / slug
        if dest_skill_dir.exists():
            raise ValidationError(f"Destination skill already exists: {dest_skill_dir}")

        related_docs = collect_related_docs(source_root, source_type, source_namespace, slug)
        doc_id_map = {
            old_doc_id: f"{dest_type}.{dest_namespace}.doc.{doc_slug}"
            for old_doc_id, doc_slug, _doc_dir in related_docs
        }

        shutil.move(str(skill_dir), str(dest_skill_dir))
        rewrite_item_id(dest_skill_dir / "item.toml", new_skill_id)
        rewrite_body_references(dest_skill_dir / "body.md", doc_id_map)

        for old_doc_id, doc_slug, doc_dir in related_docs:
            dest_doc_dir = dest_root / "docs" / doc_slug
            if dest_doc_dir.exists():
                raise ValidationError(f"Destination doc already exists: {dest_doc_dir}")
            shutil.move(str(doc_dir), str(dest_doc_dir))
            rewrite_item_id(dest_doc_dir / "item.toml", doc_id_map[old_doc_id])

        source_enabled = [item for item in source_enabled if item != old_skill_id]
        source_disabled = [item for item in source_disabled if item != old_skill_id]
        if new_skill_id not in dest_enabled:
            dest_enabled.append(new_skill_id)
        dest_disabled = [item for item in dest_disabled if item != new_skill_id]
        promoted.append(new_skill_id)

    source_config["enabled_skills"] = sorted(source_enabled)
    source_config["disabled_skills"] = sorted(source_disabled)
    dest_config["enabled_skills"] = sorted(dest_enabled)
    dest_config["disabled_skills"] = sorted(dest_disabled)
    write_toml_document(source_root / "config.toml", source_config)
    write_toml_document(dest_root / "config.toml", dest_config)
    return promoted


def promotion_checklist_warnings(
    corp_root: Path,
    user_root: Path,
    from_layer: str,
    skill_ids: list[str],
    from_repo_id: str | None = None,
    all_imported: bool = False,
) -> list[str]:
    source_root, _source_type, _source_namespace = resolve_layer_target(corp_root, user_root, from_layer, from_repo_id)
    selected_ids = resolve_selected_skill_ids(source_root, skill_ids, all_imported)
    warnings: list[str] = []
    for skill_id in selected_ids:
        _, _, _, slug = validate_canonical_id(skill_id, expected_kind="skill", path=source_root / "config.toml")
        item_path = source_root / "skills" / slug / "item.toml"
        item = read_toml(item_path)
        checklist = item.get("promotion_checklist")
        if not isinstance(checklist, dict):
            warnings.append(f"{skill_id}: missing promotion_checklist")
            continue
        missing = sorted(
            field
            for field in PROMOTION_CHECKLIST_FIELDS
            if not isinstance(checklist.get(field), str) or not str(checklist.get(field)).strip()
        )
        if missing:
            warnings.append(f"{skill_id}: missing promotion_checklist fields: {', '.join(missing)}")
    return warnings


def resolve_selected_skill_ids(source_root: Path, skill_ids: list[str], all_imported: bool) -> list[str]:
    if all_imported:
        resolved: list[str] = []
        skills_root = source_root / "skills"
        if not skills_root.exists():
            return []
        for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
            item = read_toml(skill_dir / "item.toml")
            skill_id = str(item.get("id", ""))
            if str(item.get("source_note", "")).startswith("Imported from "):
                resolved.append(skill_id)
        return resolved
    if not skill_ids:
        raise ValidationError("Specify at least one --skill-id or use --all-imported")
    return skill_ids


def resolve_layer_target(corp_root: Path, user_root: Path, layer: str, repo_id: str | None) -> tuple[Path, str, str]:
    if layer == "user":
        config = read_toml(user_root / "config.toml")
        return user_root, "user", str(config.get("id", "local"))
    if layer == "org":
        config = read_toml(corp_root / "org" / "config.toml")
        return corp_root / "org", "corp", str(config.get("id", "org"))
    if layer == "repo":
        if not repo_id:
            raise ValidationError("Repo layer requires repo id")
        config = read_toml(corp_root / "repos" / repo_id / "config.toml")
        return corp_root / "repos" / repo_id, "corp", str(config.get("id", repo_id))
    raise ValidationError(f"Unsupported layer {layer!r}")


def collect_related_docs(source_root: Path, source_type: str, source_namespace: str, skill_slug: str) -> list[tuple[str, str, Path]]:
    docs_root = source_root / "docs"
    if not docs_root.exists():
        return []
    related: list[tuple[str, str, Path]] = []
    prefix = f"{skill_slug}-"
    for doc_dir in sorted(path for path in docs_root.iterdir() if path.is_dir() and path.name.startswith(prefix)):
        doc_slug = doc_dir.name
        doc_id = f"{source_type}.{source_namespace}.doc.{doc_slug}"
        related.append((doc_id, doc_slug, doc_dir))
    return related


def rewrite_item_id(item_path: Path, new_item_id: str) -> None:
    data = read_toml(item_path)
    data["id"] = new_item_id
    write_toml_document(item_path, data)


def rewrite_body_references(body_path: Path, replacements: dict[str, str]) -> None:
    if not replacements:
        return
    body = body_path.read_text(encoding="utf-8")
    for old_id, new_id in replacements.items():
        body = body.replace(old_id, new_id)
    body_path.write_text(body, encoding="utf-8")
