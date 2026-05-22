from __future__ import annotations

import re
from pathlib import Path

from team_agents.errors import ResolutionError
from team_agents.models import Item, ResolutionResult
from team_agents.target_emission import target_included


MANAGED_START = "<!-- team-agents:start -->"
MANAGED_END = "<!-- team-agents:end -->"


def split_frontmatter(body: str) -> tuple[dict[str, str], str]:
    if not body.startswith("---\n"):
        return {}, body
    end_marker = "\n---\n"
    end_index = body.find(end_marker, 4)
    if end_index == -1:
        return {}, body
    raw_metadata = body[4:end_index]
    content = body[end_index + len(end_marker) :]
    metadata: dict[str, str] = {}
    for line in raw_metadata.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("'\"")
    return metadata, content


def infer_skill_description(body: str, item: Item) -> str:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("- ") or line.startswith("```") or line.startswith("`"):
            continue
        compact = re.sub(r"\s+", " ", line)
        return compact[:280]
    return f"Generated skill for {item.title}."


def yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_workspace_router(result: ResolutionResult) -> str:
    lines = [
        "Use the local generated context under `.agents/`.",
        "",
        "- Read `.agents/index.md` first.",
        "- Treat `.agents/` as generated local context and do not commit it.",
        "- Use `.agents/resolution.json` when you need provenance or activation details.",
    ]
    if result.workspace_context.repo_class == "client":
        lines.append("- Corporate private operational material must not be pushed into this repo.")
    return "\n".join(lines)


def merge_managed_block(existing: str, managed_content: str) -> str:
    managed_block = MANAGED_START + "\n" + managed_content + "\n" + MANAGED_END + "\n"
    if not existing.strip():
        return managed_block
    if MANAGED_START in existing and MANAGED_END in existing:
        before, remainder = existing.split(MANAGED_START, 1)
        _, after = remainder.split(MANAGED_END, 1)
        return before + MANAGED_START + "\n" + managed_content + "\n" + MANAGED_END + after
    return existing.rstrip() + "\n\n" + managed_block


def write_workspace_router_file(
    result: ResolutionResult,
    workspace_root: Path,
    repo_class: str,
    relative_path: str,
    managed_content: str | None = None,
) -> Path:
    path = workspace_root / relative_path
    routing = managed_content if managed_content is not None else render_workspace_router(result)
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if MANAGED_START in content and MANAGED_END in content:
            path.write_text(merge_managed_block(content, routing), encoding="utf-8")
            return path
        if repo_class != "internal":
            raise ResolutionError(f"Tracked {relative_path} in a client repo cannot be updated")
        path.write_text(merge_managed_block(content, routing), encoding="utf-8")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(merge_managed_block("", routing), encoding="utf-8")
    return path


def split_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text)]
