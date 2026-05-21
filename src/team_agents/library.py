from __future__ import annotations

import shutil
from pathlib import Path

from team_agents.emitters import claude, codex, cursor
from team_agents.emitters.common import merge_managed_block, resolve_tool_targets, target_included
from team_agents.errors import ValidationError
from team_agents.materialization import materialize_path
from team_agents.models import Item, MachineConfig, SourceRef


def library_root(machine_config: MachineConfig) -> Path:
    return machine_config.cache_root.parent / "library"


def seed_library(machine_config: MachineConfig, user_root: Path) -> Path:
    corp_root = machine_config.corp_repo_path.resolve()
    user_root = user_root.resolve()
    if not corp_root.exists():
        raise ValidationError(f"Corp repo path does not exist: {corp_root}")
    if not user_root.exists():
        raise ValidationError(f"Local user layer path does not exist: {user_root}")
    root = library_root(machine_config)
    root.mkdir(parents=True, exist_ok=True)
    (root / ".materialization-strategy").write_text(machine_config.materialization_strategy + "\n", encoding="utf-8")
    materialize_path(
        corp_root,
        root / "corp",
        strategy=machine_config.materialization_strategy,
        target_is_directory=True,
    )
    materialize_path(
        user_root,
        root / "user",
        strategy=machine_config.materialization_strategy,
        target_is_directory=True,
    )
    (root / "external").mkdir(parents=True, exist_ok=True)
    (root / "rendered").mkdir(parents=True, exist_ok=True)
    return root


def ensure_external_library_checkout(root: Path, source_ref: SourceRef, strategy: str = "auto") -> Path:
    external_path = root / "external" / f"{source_ref.source_id}@{source_ref.commit}"
    materialize_path(source_ref.checkout_path, external_path, strategy=strategy, target_is_directory=True)
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
    normalize_claude_skills_root(claude_root)
    claude_root.mkdir(parents=True, exist_ok=True)
    desired_slugs = {
        item.slug
        for item in skill_items
        if target_included(item, "claude")
    }
    prune_stale_claude_user_skills(root, claude_root, desired_slugs)
    written: list[Path] = []
    for item in skill_items:
        if not target_included(item, "claude"):
            continue
        library_body = write_claude_library_skill(root, item)
        target = claude_root / item.slug / "SKILL.md"
        materialize_path(
            library_body,
            target,
            strategy=global_output_strategy(root),
            target_is_directory=False,
        )
        written.append(target)
    return written


def seed_codex_user_router(root: Path, skill_items: list[Item]) -> list[Path]:
    codex_path = Path.home() / ".codex" / "AGENTS.md"
    sections: list[str] = []
    for item in skill_items:
        if not target_included(item, "codex"):
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
    desired_slugs = {
        item.slug
        for item in skill_items
        if target_included(item, "cursor")
    }
    prune_stale_cursor_user_rules(root, cursor_root, desired_slugs)
    written: list[Path] = []
    for item in skill_items:
        if not target_included(item, "cursor"):
            continue
        rendered = write_cursor_library_rule(root, item)
        target = cursor_root / f"{item.slug}.mdc"
        materialize_path(
            rendered,
            target,
            strategy=global_output_strategy(root),
            target_is_directory=False,
        )
        written.append(target)
    return written


def write_claude_library_skill(root: Path, item: Item) -> Path:
    path = root / "rendered" / "claude" / "skills" / item.slug / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(claude.render_skill_markdown(item), encoding="utf-8")
    return path


def write_cursor_library_rule(root: Path, item: Item) -> Path:
    path = root / "rendered" / "cursor" / "rules" / f"{item.slug}.mdc"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cursor.render_rule(item), encoding="utf-8")
    return path


def prune_stale_claude_user_skills(root: Path, claude_root: Path, desired_slugs: set[str]) -> None:
    rendered_root = (root / "rendered" / "claude" / "skills").resolve()
    legacy_root = (Path.home() / ".agents" / "skills").resolve()
    for skill_dir in sorted(path for path in claude_root.iterdir() if path.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_symlink():
            continue
        target = skill_md.resolve()
        managed = _is_within(target, rendered_root) or _is_within(target, legacy_root)
        if managed and skill_dir.name not in desired_slugs:
            shutil.rmtree(skill_dir)


def normalize_claude_skills_root(claude_root: Path) -> None:
    legacy_root = (Path.home() / ".agents" / "skills").resolve()
    if not claude_root.is_symlink():
        return
    target = claude_root.resolve()
    if _is_within(target, legacy_root) or target == legacy_root:
        claude_root.unlink()


def prune_stale_cursor_user_rules(root: Path, cursor_root: Path, desired_slugs: set[str]) -> None:
    rendered_root = (root / "rendered" / "cursor" / "rules").resolve()
    for rule_path in sorted(cursor_root.glob("*.mdc")):
        if not rule_path.is_symlink():
            continue
        target = rule_path.resolve()
        managed = _is_within(target, rendered_root)
        if managed and rule_path.stem not in desired_slugs:
            rule_path.unlink()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def render_codex_section(root: Path, item: Item) -> str:
    source_path = None
    if library_strategy(root) != "render-only":
        source_path = body_library_reference(root, item)
    return codex.render_global_section(item, library_body=source_path)


def render_codex_body(item: Item, body: str) -> str:
    return codex.render_body(item, body)


def render_cursor_rule(item: Item) -> str:
    return cursor.render_rule(item)


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
            strategy=library_strategy(root),
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


def library_strategy(root: Path) -> str:
    strategy_file = root / ".materialization-strategy"
    if strategy_file.exists():
        return strategy_file.read_text(encoding="utf-8").strip() or "auto"
    return "auto"


def global_output_strategy(root: Path) -> str:
    strategy = library_strategy(root)
    if strategy == "render-only":
        return "copy"
    return strategy
