from __future__ import annotations

from pathlib import Path

from team_agents.emitters.agents_md import render_agents_md_contract
from team_agents.emitters.common import split_frontmatter, split_paragraphs, write_workspace_router_file
from team_agents.models import Item, ResolutionResult


ROUTER_PATH = "AGENTS.md"


def render_global_section(item: Item, library_body: Path | None = None) -> str:
    _, body = split_frontmatter(item.body)
    lines = [
        f"## {item.title}",
    ]
    if library_body is not None:
        lines.append(f"Library body: `{library_body}`")
    text = render_body(item, body)
    if text:
        lines.extend(["", text])
    return "\n".join(lines)


def render_body(item: Item, body: str) -> str:
    text = body.strip()
    settings = item.target_settings.get("codex")
    if settings is None or settings.summary_budget != "short":
        return text
    for paragraph in split_paragraphs(text):
        if paragraph:
            return paragraph[:500]
    return text[:500]


def write_workspace_router(result: ResolutionResult, workspace_root: Path, repo_class: str) -> Path:
    return write_workspace_router_file(
        result,
        workspace_root,
        repo_class,
        ROUTER_PATH,
        managed_content=render_agents_md_contract(result),
    )

