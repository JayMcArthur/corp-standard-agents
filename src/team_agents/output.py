from __future__ import annotations

import hashlib
import json
from pathlib import Path

from team_agents.bootstrap import bootstrap_guidance_items, render_bootstrap_guidance
from team_agents.errors import ProtectionError
from team_agents.git_tools import ensure_git_exclude, has_tracked_prefix, is_tracked
from team_agents.machine import load_machine_config
from team_agents.models import Item, ResolutionResult
from team_agents.emitters import claude, codex, cursor
from team_agents.emitters.common import resolve_tool_targets
from team_agents.resolution_schema import validate_resolution_json


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
    paths.append(write_index_md(result, agents_dir))
    paths.append(write_resolution_json(result, agents_dir))
    paths.extend(write_bootstrap_output(result, agents_dir, repo_class))
    paths.extend(write_item_outputs(result, agents_dir, repo_class))
    paths.extend(write_tool_routers(result, workspace_root, repo_class, tool_targets))
    paths.append(write_artifact_manifest(result, workspace_root, paths))
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
    lines.extend(["", "## Active Contracts"])
    for item_id in result.active_contracts:
        lines.append(f"- `{item_id}`")
    evidence_lines = render_evidence_requirements(result)
    if evidence_lines:
        lines.extend(["", "## Required Evidence Before Done"])
        lines.extend(evidence_lines)
    lines.extend(["", "## Active Packs"])
    for item_id in result.active_packs:
        lines.append(f"- `{item_id}`")
    lines.extend(["", "## Active Flows"])
    for item_id in result.active_flows:
        lines.append(f"- `{item_id}`")
        resolved = result.items.get(item_id)
        if resolved is not None:
            lines.extend(render_flow_metadata_lines(resolved.item))
    lines.extend(["", "## Active Profiles"])
    for item_id in result.active_profiles:
        lines.append(f"- `{item_id}`")
    bootstrap_items = bootstrap_guidance_items(result)
    if bootstrap_items:
        lines.extend(["", "## Repo Bootstrap Guidance", "", "- Generated detail: `.agents/bootstrap.md`"])
        for resolved in bootstrap_items:
            lines.append(f"- `{resolved.item.item_id}`: {resolved.item.title}")
    lines.extend(["", "## Recommended Agent Types"])
    for agent_type in result.recommended_agent_types:
        lines.append(f"- `{agent_type}`")
    lines.extend(["", "## Recommended Items"])
    for item_id in result.recommended_items:
        lines.append(f"- `{item_id}`")
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


def render_evidence_requirements(result: ResolutionResult) -> list[str]:
    lines: list[str] = []
    for item_id in result.active_contracts + result.active_flows:
        resolved = result.items.get(item_id)
        if resolved is None or not resolved.item.evidence_required:
            continue
        lines.append(f"- `{item_id}`:")
        for evidence in resolved.item.evidence_required:
            lines.append(f"  - `{evidence}`")
    return lines


def render_flow_metadata_lines(item: Item) -> list[str]:
    lines: list[str] = []
    if item.inputs:
        lines.append("  - Inputs: " + ", ".join(f"`{value}`" for value in item.inputs))
    if item.outputs:
        lines.append("  - Outputs: " + ", ".join(f"`{value}`" for value in item.outputs))
    if item.evidence_required:
        lines.append("  - Evidence required: " + ", ".join(f"`{value}`" for value in item.evidence_required))
    if item.stop_conditions:
        lines.append("  - Stop conditions: " + ", ".join(f"`{value}`" for value in item.stop_conditions))
    return lines


def write_resolution_json(result: ResolutionResult, agents_dir: Path) -> Path:
    path = agents_dir / "resolution.json"
    payload = result.to_dict()
    validate_resolution_json(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_artifact_manifest(result: ResolutionResult, workspace_root: Path, written_paths: list[Path]) -> Path:
    agents_dir = workspace_root / ".agents"
    path = agents_dir / "artifacts.json"
    resolution_hash = source_resolution_hash(result)
    artifacts = [
        artifact_entry(
            path=written_path,
            workspace_root=workspace_root,
            repo_class=result.workspace_context.repo_class or "internal",
            resolution_hash=resolution_hash,
            tracked_router_paths=tracked_router_files(workspace_root),
        )
        for written_path in written_paths
    ]
    artifacts.append(
        {
            "path": ".agents/artifacts.json",
            "kind": "artifact-manifest",
            "target": None,
            "generated_by": "team-agents sync",
            "source_resolution_hash": resolution_hash,
            "safe_to_commit": False,
            "consumer": "machine",
            "description": "Manifest describing files generated by team-agents sync.",
        }
    )
    payload = {
        "schema_version": "v1",
        "workspace": str(workspace_root),
        "repo_class": result.workspace_context.repo_class or "unknown",
        "source_resolution_hash": resolution_hash,
        "artifacts": artifacts,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def source_resolution_hash(result: ResolutionResult) -> str:
    payload = json.dumps(result.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def artifact_entry(
    path: Path,
    workspace_root: Path,
    repo_class: str,
    resolution_hash: str,
    tracked_router_paths: list[str],
) -> dict[str, object]:
    relative = path.resolve().relative_to(workspace_root.resolve()).as_posix()
    target = artifact_target(relative)
    in_agents_dir = relative.startswith(".agents/")
    is_tracked_router = relative in tracked_router_paths
    safe_to_commit = bool(is_tracked_router and repo_class != "client" and not in_agents_dir)
    return {
        "path": relative,
        "kind": artifact_kind(relative),
        "target": target,
        "generated_by": "team-agents sync",
        "source_resolution_hash": resolution_hash,
        "safe_to_commit": safe_to_commit,
        "consumer": artifact_consumer(relative, target),
        "description": artifact_description(relative),
    }


def artifact_target(relative: str) -> str | None:
    for target, router_path in ROUTER_TARGETS.items():
        if relative == router_path:
            return target
    return None


def artifact_kind(relative: str) -> str:
    if relative == ".agents/index.md":
        return "context-index"
    if relative == ".agents/resolution.json":
        return "resolution"
    if relative == ".agents/bootstrap.md":
        return "bootstrap-guidance"
    if relative.startswith(".agents/skills/"):
        return "skill"
    if relative.startswith(".agents/policies/"):
        return "policy"
    if relative.startswith(".agents/docs/"):
        return "doc"
    if relative in ROUTER_FILES:
        return "tool-router"
    return "generated-artifact"


def artifact_consumer(relative: str, target: str | None) -> str:
    if target is not None:
        return target
    if relative in {".agents/resolution.json", ".agents/artifacts.json"}:
        return "machine"
    return "human-and-agent"


def artifact_description(relative: str) -> str:
    if relative == ".agents/index.md":
        return "Human-readable summary of active standards for this workspace."
    if relative == ".agents/resolution.json":
        return "Machine-readable resolved context, provenance, warnings, and denied items."
    if relative == ".agents/bootstrap.md":
        return "One-time bootstrap and minimal verification guidance."
    if relative.startswith(".agents/skills/"):
        return "Generated skill body selected for this workspace."
    if relative.startswith(".agents/policies/"):
        return "Generated policy body selected for this workspace."
    if relative.startswith(".agents/docs/"):
        return "Generated documentation selected for this workspace."
    if relative == ROUTER_TARGETS["codex"]:
        return "Codex router file pointing to generated team-agents context."
    if relative == ROUTER_TARGETS["claude"]:
        return "Claude router file pointing to generated team-agents context."
    if relative == ROUTER_TARGETS["cursor"]:
        return "Cursor rule pointing to generated team-agents context."
    return "Generated team-agents artifact."


def write_bootstrap_output(result: ResolutionResult, agents_dir: Path, repo_class: str) -> list[Path]:
    bootstrap_items = [
        resolved
        for resolved in bootstrap_guidance_items(result)
        if not (repo_class == "client" and resolved.item.privacy == "corp-private")
    ]
    if not bootstrap_items:
        return []
    path = agents_dir / "bootstrap.md"
    path.write_text(render_bootstrap_guidance(bootstrap_items), encoding="utf-8")
    return [path]


def write_item_outputs(result: ResolutionResult, agents_dir: Path, repo_class: str) -> list[Path]:
    written: list[Path] = []
    for resolved in sorted(result.items.values(), key=lambda value: value.item.item_id):
        if repo_class == "client" and resolved.item.privacy == "corp-private":
            continue
        if resolved.item.kind == "skill":
            path = agents_dir / "skills" / resolved.item.slug / "SKILL.md"
        elif resolved.item.kind == "policy":
            path = agents_dir / "policies" / f"{resolved.item.slug}.md"
        elif resolved.item.kind == "doc":
            path = agents_dir / "docs" / f"{resolved.item.slug}.md"
        else:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        content = render_output_body(resolved.item)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def render_output_body(item: Item) -> str:
    if item.kind != "skill":
        return item.body
    return claude.render_skill_markdown(item)


def write_tool_routers(
    result: ResolutionResult,
    workspace_root: Path,
    repo_class: str,
    tool_targets: list[str],
) -> list[Path]:
    paths: list[Path] = []
    emitters = {
        "codex": codex.write_workspace_router,
        "claude": claude.write_workspace_router,
        "cursor": cursor.write_workspace_router,
    }
    for target in tool_targets:
        paths.append(emitters[target](result, workspace_root, repo_class))
    return paths


def tracked_router_files(git_root: Path) -> list[str]:
    return [name for name in ROUTER_FILES if is_tracked(git_root, name)]
