from __future__ import annotations

from pathlib import Path

from team_agents.emitters.common import infer_skill_description, split_frontmatter, write_workspace_router_file
from team_agents.frontmatter import dump_frontmatter_value
from team_agents.models import Item, ResolutionResult


ROUTER_PATH = ".cursor/rules/team-agents.mdc"


def render_rule(item: Item) -> str:
    _, body = split_frontmatter(item.body)
    description = item.source_note or infer_skill_description(body, item)
    metadata: list[tuple[str, object]] = [("description", description)]
    cursor_settings = item.target_settings.get("cursor")
    cursor_globs = cursor_settings.globs if cursor_settings and cursor_settings.globs else item.cursor_globs
    cursor_always_apply = (
        cursor_settings.always_apply
        if cursor_settings and cursor_settings.always_apply is not None
        else item.cursor_always_apply
    )
    if cursor_globs:
        metadata.append(("globs", cursor_globs))
    if cursor_always_apply is not None:
        metadata.append(("alwaysApply", cursor_always_apply))
    lines = ["---"]
    for key, value in metadata:
        lines.append(f"{key}: {dump_frontmatter_value(value)}")
    lines.extend(["---", "", body.strip()])
    return "\n".join(lines).rstrip() + "\n"


def write_workspace_router(result: ResolutionResult, workspace_root: Path, repo_class: str) -> Path:
    return write_workspace_router_file(result, workspace_root, repo_class, ROUTER_PATH)
