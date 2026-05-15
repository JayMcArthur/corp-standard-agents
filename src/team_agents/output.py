from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from team_agents.errors import ProtectionError, ResolutionError
from team_agents.git_tools import ensure_git_exclude, has_tracked_prefix, is_tracked
from team_agents.machine import load_machine_config
from team_agents.models import Item, ResolutionResult
from team_agents.resolution_schema import validate_resolution_json


MANAGED_START = "<!-- team-agents:start -->"
MANAGED_END = "<!-- team-agents:end -->"
ROUTER_TARGETS = {
    "codex": "AGENTS.md",
    "claude": "CLAUDE.md",
    "cursor": ".cursor/rules/team-agents.mdc",
}
ROUTER_FILES = tuple(ROUTER_TARGETS.values())


def write_sync_output(result: ResolutionResult) -> list[Path]:
    workspace_root = result.workspace_context.git_root or result.workspace_context.workspace
    repo_class = result.workspace_context.repo_class or "internal"
    ensure_write_safety(result, workspace_root)
    machine_config = load_machine_config()
    tool_targets = resolve_tool_targets(machine_config.default_tool_target)
    agents_dir = workspace_root / ".agents"
    paths: list[Path] = []
    agents_dir.mkdir(parents=True, exist_ok=True)
    prune_stale_item_outputs(agents_dir)
    paths.append(write_index_md(result, agents_dir))
    paths.append(write_resolution_json(result, agents_dir))
    paths.extend(write_item_outputs(result, agents_dir, repo_class))
    paths.extend(write_tool_routers(result, workspace_root, repo_class, tool_targets))
    return paths


def ensure_write_safety(result: ResolutionResult, workspace_root: Path) -> None:
    git_root = result.workspace_context.git_root
    if git_root is None:
        return
    if has_tracked_prefix(git_root, ".agents"):
        raise ProtectionError("Tracked .agents content already exists; refusing generated output")
    entries = ["/.agents/", ".agents/"]
    for router_name in ROUTER_FILES:
        if router_name not in tracked_router_files(git_root):
            entries.append(f"/{router_name}")
    ensure_git_exclude(git_root, entries)


def write_index_md(result: ResolutionResult, agents_dir: Path) -> Path:
    lines = [
        "# Team Agents Context",
        "",
        f"- Workspace: `{result.workspace_context.workspace}`",
        f"- Repo: `{result.workspace_context.matched_repo_id or 'unknown'}`",
        f"- Repo group: `{result.workspace_context.matched_repo_group_id or 'none'}`",
        f"- Repo class: `{result.workspace_context.repo_class or 'unknown'}`",
        "",
        "## Active Sources",
    ]
    for source_id in result.enabled_sources:
        detail = result.source_details.get(source_id)
        if detail is None:
            lines.append(f"- `{source_id}`")
        else:
            lines.append(
                f"- `{source_id}`: `{detail.commit}` `{detail.trust_status}` `{detail.fingerprint[:12]}`"
            )
    lines.extend(
        [
            "",
        "## Active Skills",
        ]
    )
    for item_id in result.enabled_skills:
        lines.append(f"- `{item_id}`")
    lines.extend(["", "## Active Policies"])
    for item_id in result.active_policies:
        lines.append(f"- `{item_id}`")
    lines.extend(["", "## Active Docs"])
    for item_id in result.active_docs:
        lines.append(f"- `{item_id}`")
    lines.extend(["", "## Recommended Agent Types"])
    for agent_type in result.recommended_agent_types:
        lines.append(f"- `{agent_type}`")
    if result.denied_items:
        lines.extend(["", "## Denied Items"])
        for item_id, denied in sorted(result.denied_items.items()):
            reason = denied.denied_reason or "disabled or denied"
            lines.append(f"- `{item_id}`: {reason}")
    if result.warnings:
        lines.extend(["", "## Warnings"])
        for warning in result.warnings:
            lines.append(f"- {warning}")
    path = agents_dir / "index.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_resolution_json(result: ResolutionResult, agents_dir: Path) -> Path:
    path = agents_dir / "resolution.json"
    payload = result.to_dict()
    validate_resolution_json(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_item_outputs(result: ResolutionResult, agents_dir: Path, repo_class: str) -> list[Path]:
    written: list[Path] = []
    for resolved in sorted(result.items.values(), key=lambda value: value.item.item_id):
        if repo_class == "client" and resolved.item.privacy == "corp-private":
            continue
        if resolved.item.kind == "skill":
            path = agents_dir / "skills" / resolved.item.slug / "SKILL.md"
        elif resolved.item.kind == "policy":
            path = agents_dir / "policies" / f"{resolved.item.slug}.md"
        else:
            path = agents_dir / "docs" / f"{resolved.item.slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = render_output_body(resolved.item)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def prune_stale_item_outputs(agents_dir: Path) -> None:
    for name in ["skills", "policies", "docs"]:
        target = agents_dir / name
        if target.exists():
            shutil.rmtree(target)


def render_output_body(item: Item) -> str:
    if item.kind != "skill":
        return item.body
    return render_skill_markdown(item)


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


def write_tool_routers(
    result: ResolutionResult,
    workspace_root: Path,
    repo_class: str,
    tool_targets: list[str],
) -> list[Path]:
    paths: list[Path] = []
    for target in tool_targets:
        router_name = ROUTER_TARGETS[target]
        paths.append(write_router_file(result, workspace_root, repo_class, router_name))
    return paths


def write_router_file(result: ResolutionResult, workspace_root: Path, repo_class: str, router_name: str) -> Path:
    path = workspace_root / router_name
    routing = build_routing_block(result)
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if MANAGED_START in content and MANAGED_END in content:
            before, remainder = content.split(MANAGED_START, 1)
            _, after = remainder.split(MANAGED_END, 1)
            new_content = before + MANAGED_START + "\n" + routing + "\n" + MANAGED_END + after
            path.write_text(new_content, encoding="utf-8")
            return path
        if repo_class != "internal":
            raise ResolutionError(f"Tracked {router_name} in a client repo cannot be updated")
        new_content = content.rstrip() + "\n\n" + MANAGED_START + "\n" + routing + "\n" + MANAGED_END + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content, encoding="utf-8")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(routing + "\n", encoding="utf-8")
    return path


def build_routing_block(result: ResolutionResult) -> str:
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


def resolve_tool_targets(default_tool_target: str) -> list[str]:
    if default_tool_target == "all":
        return ["codex", "claude", "cursor"]
    if default_tool_target in {"codex", "claude", "cursor"}:
        return [default_tool_target]
    raise ResolutionError(f"Unsupported tool target {default_tool_target!r}")


def tracked_router_files(git_root: Path) -> list[str]:
    return [name for name in ROUTER_FILES if is_tracked(git_root, name)]
