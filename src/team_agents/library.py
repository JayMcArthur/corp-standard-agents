from __future__ import annotations

import shutil
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.frontmatter import dump_frontmatter_value
from team_agents.models import Item, MachineConfig, SourceRef
from team_agents.output import (
    MANAGED_END,
    MANAGED_START,
    infer_skill_description,
    render_skill_markdown,
    resolve_tool_targets,
    split_frontmatter,
)


def library_root(machine_config: MachineConfig) -> Path:
    return machine_config.cache_root.parent / "library"


def seed_library(machine_config: MachineConfig, user_root: Path) -> Path:
    corp_root = machine_config.corp_repo_path.resolve()
    user_root = user_root.resolve()
    if not corp_root.exists():
        raise ValidationError(f"Corp repo path does not exist: {corp_root}")
    if not user_root.exists():
        raise ValidationError(f"User profile path does not exist: {user_root}")
    root = library_root(machine_config)
    root.mkdir(parents=True, exist_ok=True)
    ensure_symlink(root / "corp", corp_root, target_is_directory=True)
    ensure_symlink(root / "user", user_root, target_is_directory=True)
    (root / "external").mkdir(parents=True, exist_ok=True)
    (root / "rendered").mkdir(parents=True, exist_ok=True)
    return root


def ensure_external_library_checkout(root: Path, source_ref: SourceRef) -> Path:
    external_path = root / "external" / f"{source_ref.source_id}@{source_ref.commit}"
    ensure_symlink(external_path, source_ref.checkout_path, target_is_directory=True)
    return external_path

def seed_user_global_outputs(machine_config: MachineConfig, user_root: Path, skill_items: list[Item]) -> list[Path]:
    root = seed_library(machine_config, user_root)
    targets = set(resolve_tool_targets(machine_config.default_tool_target))
    written: list[Path] = []
    if "claude" in targets:
        written.extend(seed_claude_user_skills(root, skill_items))
    if "codex" in targets:
        written.extend(seed_codex_user_router(root, skill_items))
    if "cursor" in targets:
        written.extend(seed_cursor_user_rules(root, skill_items))
    return written


def seed_claude_user_skills(root: Path, skill_items: list[Item]) -> list[Path]:
    claude_root = Path.home() / ".claude" / "skills"
    claude_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for item in skill_items:
        if item.target_tools and "claude" not in item.target_tools:
            continue
        library_body = write_claude_library_skill(root, item)
        target = claude_root / item.slug / "SKILL.md"
        ensure_symlink(target, library_body, target_is_directory=False)
        written.append(target)
    return written


def seed_codex_user_router(root: Path, skill_items: list[Item]) -> list[Path]:
    codex_path = Path.home() / ".codex" / "AGENTS.md"
    sections: list[str] = []
    for item in skill_items:
        if item.target_tools and "codex" not in item.target_tools:
            continue
        sections.append(render_codex_section(root, item))
    managed = "\n\n".join(sections).strip()
    content = merge_managed_block(codex_path.read_text(encoding="utf-8") if codex_path.exists() else "", managed)
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(content, encoding="utf-8")
    return [codex_path]


def seed_cursor_user_rules(root: Path, skill_items: list[Item]) -> list[Path]:
    cursor_root = Path.home() / ".cursor" / "rules"
    cursor_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for item in skill_items:
        if item.target_tools and "cursor" not in item.target_tools:
            continue
        rendered = write_cursor_library_rule(root, item)
        target = cursor_root / f"{item.slug}.mdc"
        ensure_symlink(target, rendered, target_is_directory=False)
        written.append(target)
    return written


def write_claude_library_skill(root: Path, item: Item) -> Path:
    path = root / "rendered" / "claude" / "skills" / item.slug / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_skill_markdown(item), encoding="utf-8")
    return path


def write_cursor_library_rule(root: Path, item: Item) -> Path:
    path = root / "rendered" / "cursor" / "rules" / f"{item.slug}.mdc"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_cursor_rule(item), encoding="utf-8")
    return path


def render_codex_section(root: Path, item: Item) -> str:
    _, body = split_frontmatter(item.body)
    source_path = body_library_reference(root, item)
    lines = [
        f"## {item.title}",
        f"Library body: `{source_path}`",
    ]
    text = body.strip()
    if text:
        lines.extend(["", text])
    return "\n".join(lines)


def render_cursor_rule(item: Item) -> str:
    _, body = split_frontmatter(item.body)
    description = item.source_note or infer_skill_description(body, item)
    metadata: list[tuple[str, object]] = [("description", description)]
    if item.cursor_globs:
        metadata.append(("globs", item.cursor_globs))
    if item.cursor_always_apply is not None:
        metadata.append(("alwaysApply", item.cursor_always_apply))
    lines = ["---"]
    for key, value in metadata:
        lines.append(f"{key}: {dump_frontmatter_value(value)}")
    lines.extend(["---", "", body.strip()])
    return "\n".join(lines).rstrip() + "\n"


def body_library_reference(root: Path, item: Item) -> Path:
    resolved_path = item.body_path.resolve()
    parts = resolved_path.parts
    if "sources" in parts:
        sources_index = parts.index("sources")
        source_id = parts[sources_index + 1]
        commit = parts[sources_index + 2]
        checkout_root = Path(*parts[: sources_index + 4])
        library_external = ensure_external_library_checkout(
            root,
            SourceRef(
                source_id=source_id,
                source_type=item.source_type,
                namespace=item.source_namespace,
                commit=commit,
                checkout_path=checkout_root,
                url="",
                fingerprint="",
                fingerprint_mode="computed",
                trust_status="verified-pinned-commit",
            ),
        )
        return library_external / resolved_path.relative_to(checkout_root)
    source_root = Path(item.source_ref).resolve()
    if item.source_type == "user":
        base = root / "user"
    elif item.source_type == "corp":
        base = root / "corp"
    else:
        return resolved_path
    return base / item.body_path.resolve().relative_to(source_root)


def merge_managed_block(existing: str, managed_content: str) -> str:
    managed_block = MANAGED_START + "\n" + managed_content + "\n" + MANAGED_END + "\n"
    if not existing.strip():
        return managed_block
    if MANAGED_START in existing and MANAGED_END in existing:
        before, remainder = existing.split(MANAGED_START, 1)
        _, after = remainder.split(MANAGED_END, 1)
        return before + MANAGED_START + "\n" + managed_content + "\n" + MANAGED_END + after
    return existing.rstrip() + "\n\n" + managed_block


def ensure_symlink(path: Path, target: Path, *, target_is_directory: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        if path.resolve() == target.resolve():
            return
        path.unlink()
    elif path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    path.symlink_to(target, target_is_directory=target_is_directory)
