from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from team_agents.errors import ValidationError
from team_agents.frontmatter import parse_frontmatter_document
from team_agents.models import Item

TrustLevelFor = Callable[[dict[str, Any], str, Any, Path], str]


def load_claude_native_items(
    layer_root: Path,
    source_type: str,
    source_namespace: str,
    *,
    trust_level_for: TrustLevelFor,
) -> dict[str, Item]:
    items: dict[str, Item] = {}
    for skill_md in iter_claude_native_skill_files(layer_root):
        slug = skill_md.parent.name
        raw_text = skill_md.read_text(encoding="utf-8")
        metadata, _ = parse_frontmatter_document(raw_text, skill_md)
        name = str(metadata.get("name") or "").strip()
        if not name:
            raise ValidationError(f"Claude-native skill is missing required frontmatter field 'name' in {skill_md}")
        tools = metadata.get("tools", [])
        if tools and not isinstance(tools, list):
            raise ValidationError(f"Claude-native frontmatter field 'tools' must be a list in {skill_md}")
        item_id = f"{source_type}.{source_namespace}.skill.{slug}"
        items[item_id] = Item(
            item_id=item_id,
            kind="skill",
            title=name,
            privacy="repo-safe",
            source_type=source_type,
            source_namespace=source_namespace,
            source_ref=str(layer_root),
            body=raw_text,
            slug=slug,
            item_path=skill_md,
            body_path=skill_md,
            target_tools=[str(tool) for tool in tools],
            claude_model=str(metadata["model"]) if metadata.get("model") else None,
            usage_mode=str(metadata.get("usage_mode", "reusable")),
            trust_level=trust_level_for({}, source_type, None, skill_md),
        )
    return items


def iter_claude_native_skill_files(layer_root: Path) -> list[Path]:
    seen: set[Path] = set()
    skill_files: list[Path] = []

    def add(skill_md: Path) -> None:
        resolved = skill_md.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        skill_files.append(skill_md)

    for skill_dir in sorted(path for path in layer_root.iterdir() if path.is_dir() and not path.name.startswith(".")):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            add(skill_md)

    for relative_root in ("skills", ".claude/skills", ".agents/skills"):
        native_root = layer_root / relative_root
        if not native_root.exists():
            continue
        for skill_md in sorted(native_root.rglob("SKILL.md")):
            if any(part == "deprecated" for part in skill_md.relative_to(native_root).parts):
                continue
            add(skill_md)

    return skill_files


def load_cursor_native_items(
    layer_root: Path,
    source_type: str,
    source_namespace: str,
    *,
    trust_level_for: TrustLevelFor,
) -> dict[str, Item]:
    items: dict[str, Item] = {}
    rules_root = layer_root / ".cursor" / "rules"
    if not rules_root.exists():
        return items
    for path in sorted(rules_root.glob("*.mdc")):
        raw_text = path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter_document(raw_text, path)
        description = str(metadata.get("description") or "").strip()
        if not description:
            raise ValidationError(f"Cursor-native rule is missing required frontmatter field 'description' in {path}")
        globs = metadata.get("globs", [])
        if globs and not isinstance(globs, list):
            raise ValidationError(f"Cursor-native frontmatter field 'globs' must be a list in {path}")
        always_apply = metadata.get("alwaysApply")
        if always_apply is not None and not isinstance(always_apply, bool):
            raise ValidationError(f"Cursor-native frontmatter field 'alwaysApply' must be a boolean in {path}")
        slug = path.stem
        item_id = f"{source_type}.{source_namespace}.skill.{slug}"
        items[item_id] = Item(
            item_id=item_id,
            kind="skill",
            title=slug.replace("-", " ").title(),
            privacy="repo-safe",
            source_type=source_type,
            source_namespace=source_namespace,
            source_ref=str(layer_root),
            body=body.strip() + "\n",
            slug=slug,
            item_path=path,
            body_path=path,
            target_tools=["cursor"],
            cursor_globs=[str(glob) for glob in globs],
            cursor_always_apply=always_apply,
            source_note=description,
            usage_mode=str(metadata.get("usage_mode", "reusable")),
            trust_level=trust_level_for({}, source_type, description, path),
        )
    return items
