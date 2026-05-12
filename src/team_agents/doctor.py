from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from team_agents.errors import TeamAgentsError
from team_agents.git_tools import find_git_root, has_tracked_prefix, is_tracked
from team_agents.models import MachineConfig, ResolutionResult
from team_agents.output import MANAGED_END, MANAGED_START


def run_doctor(
    machine_config: MachineConfig,
    workspace: Path,
    corp_root: Path,
    user_root: Path,
    resolution: ResolutionResult | None,
    load_error: TeamAgentsError | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    git_root = find_git_root(workspace)
    checks: list[dict[str, str]] = []

    def add_check(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    add_check(
        "machine-config",
        "ok" if machine_config.default_tool_target == "codex" else "warn",
        f"tool target is {machine_config.default_tool_target}",
    )
    add_check("corp-repo-path", "ok" if corp_root.exists() else "fail", str(corp_root))
    add_check("user-overrides-path", "ok" if user_root.exists() else "fail", str(user_root))

    cache_parent = machine_config.cache_root.parent
    if cache_parent.exists() and os.access(cache_parent, os.W_OK):
        add_check("cache-root-parent", "ok", str(cache_parent))
    else:
        add_check("cache-root-parent", "warn", f"cache parent may not be writable: {cache_parent}")

    if load_error is not None:
        add_check("load-and-resolve", "fail", str(load_error))
    else:
        add_check("load-and-resolve", "ok", "corp repo, user overrides, and workspace resolved")

    if git_root is None:
        add_check("workspace-git", "ok", "workspace is non-git")
    else:
        add_check("workspace-git", "ok", f"git root: {git_root}")
        if has_tracked_prefix(git_root, ".agents"):
            add_check("tracked-generated-content", "fail", "tracked .agents content blocks sync")
        else:
            add_check("tracked-generated-content", "ok", "no tracked .agents content")
        agents_tracked = is_tracked(git_root, "AGENTS.md")
        if agents_tracked:
            add_check("tracked-agents-md", "warn", "tracked AGENTS.md exists")
            path = git_root / "AGENTS.md"
            if path.exists():
                content = path.read_text(encoding="utf-8")
                if MANAGED_START in content and MANAGED_END in content:
                    add_check("managed-block", "ok", "AGENTS.md contains managed block markers")
                else:
                    add_check("managed-block", "warn", "AGENTS.md is tracked without managed block markers")
        else:
            add_check("tracked-agents-md", "ok", "AGENTS.md is untracked or absent")

    summary = {
        "ok": sum(1 for check in checks if check["status"] == "ok"),
        "warn": sum(1 for check in checks if check["status"] == "warn"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
    }

    result: dict[str, Any] = {
        "machine_config": {
            "corp_repo_path": str(machine_config.corp_repo_path),
            "user_override_path": str(machine_config.user_override_path),
            "cache_root": str(machine_config.cache_root),
            "default_tool_target": machine_config.default_tool_target,
        },
        "workspace": {
            "path": str(workspace),
            "git_root": str(git_root) if git_root else None,
        },
        "summary": summary,
        "checks": checks,
    }
    if resolution is not None:
        result["resolution"] = {
            "matched_repo_id": resolution.workspace_context.matched_repo_id,
            "matched_repo_group_id": resolution.workspace_context.matched_repo_group_id,
            "repo_class": resolution.workspace_context.repo_class,
            "is_unknown": resolution.workspace_context.is_unknown,
            "is_non_git": resolution.workspace_context.is_non_git,
            "enabled_sources": resolution.enabled_sources,
            "source_details": {
                source_id: {
                    "commit": source_ref.commit,
                    "url": source_ref.url,
                    "fingerprint": source_ref.fingerprint,
                    "fingerprint_mode": source_ref.fingerprint_mode,
                    "trust_status": source_ref.trust_status,
                }
                for source_id, source_ref in sorted(resolution.source_details.items())
            },
            "enabled_skills": resolution.enabled_skills,
            "active_policies": resolution.active_policies,
            "active_docs": resolution.active_docs,
            "recommended_agent_types": resolution.recommended_agent_types,
            "warnings": resolution.warnings,
            "denied_items": {
                item_id: resolved.denied_reason or "disabled or denied"
                for item_id, resolved in sorted(resolution.denied_items.items())
            },
        }
    return result


def doctor_text(report: dict[str, Any]) -> str:
    lines = [
        f"workspace: {report['workspace']['path']}",
        f"git-root: {report['workspace']['git_root'] or 'none'}",
        (
            "summary: "
            f"{report['summary']['ok']} ok, "
            f"{report['summary']['warn']} warn, "
            f"{report['summary']['fail']} fail"
        ),
        "",
        "checks:",
    ]
    for check in report["checks"]:
        lines.append(f"- [{check['status']}] {check['name']}: {check['detail']}")
    if "resolution" in report:
        resolution = report["resolution"]
        lines.extend(
            [
                "",
                f"matched-repo: {resolution['matched_repo_id'] or 'unknown'}",
                f"matched-repo-group: {resolution['matched_repo_group_id'] or 'none'}",
                f"repo-class: {resolution['repo_class'] or 'unknown'}",
                f"sources: {', '.join(resolution['enabled_sources']) or 'none'}",
                f"skills: {', '.join(resolution['enabled_skills']) or 'none'}",
                f"policies: {', '.join(resolution['active_policies']) or 'none'}",
                f"docs: {', '.join(resolution['active_docs']) or 'none'}",
            ]
        )
        if resolution["denied_items"]:
            lines.append(f"denied-items: {', '.join(f'{key} ({value})' for key, value in resolution['denied_items'].items())}")
    return "\n".join(lines)


def doctor_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
