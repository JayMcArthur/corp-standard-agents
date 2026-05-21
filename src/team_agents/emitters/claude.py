from __future__ import annotations

from pathlib import Path

from team_agents.emitters.common import infer_skill_description, split_frontmatter, write_workspace_router_file, yaml_scalar
from team_agents.models import Item, ResolutionResult


ROUTER_PATH = "CLAUDE.md"


def render_skill_markdown(item: Item) -> str:
    metadata, body = split_frontmatter(item.body)
    name = str(metadata.get("name") or item.slug)
    description = str(metadata.get("description") or infer_skill_description(body, item))
    lines = [
        "---",
        f"name: {yaml_scalar(name)}",
        f"description: {yaml_scalar(description)}",
        "---",
        "",
        body.strip(),
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_workspace_router(result: ResolutionResult, workspace_root: Path, repo_class: str) -> Path:
    return write_workspace_router_file(result, workspace_root, repo_class, ROUTER_PATH)
