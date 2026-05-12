from __future__ import annotations

import json
from pathlib import Path

from team_agents.errors import ProtectionError, ResolutionError
from team_agents.git_tools import ensure_git_exclude, has_tracked_prefix, is_tracked
from team_agents.models import ResolutionResult


MANAGED_START = "<!-- team-agents:start -->"
MANAGED_END = "<!-- team-agents:end -->"


def write_sync_output(result: ResolutionResult) -> list[Path]:
    workspace_root = result.workspace_context.git_root or result.workspace_context.workspace
    repo_class = result.workspace_context.repo_class or "internal"
    ensure_write_safety(result, workspace_root)
    agents_dir = workspace_root / ".agents"
    paths: list[Path] = []
    agents_dir.mkdir(parents=True, exist_ok=True)
    paths.append(write_index_md(result, agents_dir))
    paths.append(write_resolution_json(result, agents_dir))
    paths.extend(write_item_outputs(result, agents_dir, repo_class))
    paths.append(write_agents_router(result, workspace_root, repo_class))
    return paths


def ensure_write_safety(result: ResolutionResult, workspace_root: Path) -> None:
    git_root = result.workspace_context.git_root
    if git_root is None:
        return
    if has_tracked_prefix(git_root, ".agents"):
        raise ProtectionError("Tracked .agents content already exists; refusing generated output")
    agents_tracked = is_tracked(git_root, "AGENTS.md")
    if result.workspace_context.repo_class == "client" and agents_tracked:
        raise ResolutionError("Tracked AGENTS.md in a client repo blocks repo-local generated output")
    entries = ["/.agents/", ".agents/"]
    if not agents_tracked:
        entries.append("/AGENTS.md")
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
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        path.write_text(resolved.item.body, encoding="utf-8")
        written.append(path)
    return written


def write_agents_router(result: ResolutionResult, workspace_root: Path, repo_class: str) -> Path:
    path = workspace_root / "AGENTS.md"
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
            raise ResolutionError("Tracked AGENTS.md in a client repo cannot be updated")
        new_content = content.rstrip() + "\n\n" + MANAGED_START + "\n" + routing + "\n" + MANAGED_END + "\n"
        path.write_text(new_content, encoding="utf-8")
        return path
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
