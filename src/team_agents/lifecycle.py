from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from team_agents.errors import TeamAgentsError
from team_agents.git_tools import find_git_root, run_git
from team_agents.library import ensure_external_library_checkout, library_root, seed_library, seed_user_global_outputs
from team_agents.loaders import load_corp_repo, load_user_layer
from team_agents.models import CorpRepo, MachineConfig, ResolutionResult, SourceRef, UserLayer
from team_agents.output import write_sync_output
from team_agents.resolution import resolve_user_global, resolve_workspace
from team_agents.sources import materialize_source


def recent_workspaces_path(machine_config: MachineConfig) -> Path:
    return machine_config.cache_root / "state" / "recent_workspaces.json"


def update_log_path(machine_config: MachineConfig) -> Path:
    return machine_config.cache_root / "logs" / "update.json"


def write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_recent_workspaces(machine_config: MachineConfig) -> list[Path]:
    path = recent_workspaces_path(machine_config)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    workspaces = data.get("workspaces", [])
    if not isinstance(workspaces, list):
        return []
    return [Path(str(item)).expanduser().resolve() for item in workspaces]


def record_recent_workspace(machine_config: MachineConfig, workspace: Path) -> Path:
    workspaces = [path for path in load_recent_workspaces(machine_config) if path != workspace.resolve()]
    workspaces.insert(0, workspace.resolve())
    payload = {"workspaces": [str(path) for path in workspaces[:20]]}
    return write_json(recent_workspaces_path(machine_config), payload)


def _active_skill_items(result: ResolutionResult) -> list:
    return [
        resolved.item
        for _, resolved in sorted(result.items.items())
        if resolved.item.kind == "skill" and resolved.active
    ]


def refresh_declared_sources(
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserLayer,
) -> dict[str, SourceRef]:
    source_details: dict[str, SourceRef] = {}
    for source_id, source in sorted(corp.sources.items()):
        source_details[source_id] = materialize_source(source, machine_config)
    for source_id, source in sorted(user.personal_sources.items()):
        source_details[source_id] = materialize_source(source, machine_config)
    return source_details


def gc_stale_external_checkouts(machine_config: MachineConfig, active_source_details: dict[str, SourceRef]) -> dict[str, list[str]]:
    active_cache_keys = {
        (source_ref.source_id, source_ref.commit)
        for source_ref in active_source_details.values()
    }
    active_library_names = {f"{source_id}@{commit}" for source_id, commit in active_cache_keys}
    removed_cache: list[str] = []
    removed_library: list[str] = []

    sources_root = machine_config.cache_root / "sources"
    if sources_root.exists():
        for source_dir in sorted(path for path in sources_root.iterdir() if path.is_dir()):
            for commit_dir in sorted(path for path in source_dir.iterdir() if path.is_dir()):
                key = (source_dir.name, commit_dir.name)
                if key not in active_cache_keys:
                    shutil.rmtree(commit_dir)
                    removed_cache.append(str(commit_dir))
            if not any(source_dir.iterdir()):
                source_dir.rmdir()

    external_root = library_root(machine_config) / "external"
    if external_root.exists():
        for entry in sorted(external_root.iterdir()):
            if entry.name not in active_library_names:
                if entry.is_symlink() or entry.is_file():
                    entry.unlink()
                elif entry.is_dir():
                    shutil.rmtree(entry)
                removed_library.append(str(entry))

    return {"cache": removed_cache, "library": removed_library}


def reseed(
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserLayer,
    *,
    workspaces: list[Path] | None = None,
    include_recent_workspaces: bool = True,
) -> dict[str, object]:
    root = seed_library(machine_config, user.root)
    global_result = resolve_user_global(machine_config, corp, user)
    active_sources = dict(global_result.source_details)
    for source_ref in global_result.source_details.values():
        ensure_external_library_checkout(root, source_ref, strategy=machine_config.materialization_strategy)
    user_global_written = seed_user_global_outputs(machine_config, user.root, _active_skill_items(global_result))

    workspace_paths: list[Path] = []
    if workspaces:
        workspace_paths.extend(path.resolve() for path in workspaces)
    if include_recent_workspaces:
        workspace_paths.extend(load_recent_workspaces(machine_config))

    seen: set[Path] = set()
    workspace_summaries: list[dict[str, object]] = []
    for workspace in workspace_paths:
        workspace = workspace.resolve()
        if workspace in seen or not workspace.exists():
            continue
        seen.add(workspace)
        result = resolve_workspace(workspace, machine_config, corp, user)
        active_sources.update(result.source_details)
        written = write_sync_output(result)
        record_recent_workspace(machine_config, workspace)
        workspace_summaries.append(
            {
                "workspace": str(workspace),
                "matched_repo_id": result.workspace_context.matched_repo_id,
                "written": [str(path) for path in written],
            }
        )
        for source_ref in result.source_details.values():
            ensure_external_library_checkout(root, source_ref, strategy=machine_config.materialization_strategy)

    stale = gc_stale_external_checkouts(machine_config, active_sources)
    return {
        "global_written": [str(path) for path in user_global_written],
        "workspaces": workspace_summaries,
        "source_details": {
            source_id: {
                "commit": source_ref.commit,
                "checkout_path": str(source_ref.checkout_path),
                "trust_status": source_ref.trust_status,
            }
            for source_id, source_ref in sorted(active_sources.items())
        },
        "stale_removed": stale,
    }


def run_update(machine_config: MachineConfig) -> dict[str, object]:
    corp_root = machine_config.corp_repo_path
    if find_git_root(corp_root) != corp_root.resolve():
        raise TeamAgentsError(f"Corp repo is not a git checkout: {corp_root}")

    before_commit = run_git(["rev-parse", "HEAD"], cwd=corp_root)
    pull_output = run_git(["pull", "--ff-only"], cwd=corp_root)
    after_commit = run_git(["rev-parse", "HEAD"], cwd=corp_root)

    corp = load_corp_repo(corp_root)
    user = load_user_layer(machine_config.user_layer_path)
    refreshed_sources = refresh_declared_sources(machine_config, corp, user)
    reseed_summary = reseed(machine_config, corp, user, include_recent_workspaces=True)
    payload = {
        "ran_at": datetime.now(UTC).isoformat(),
        "corp_before_commit": before_commit,
        "corp_after_commit": after_commit,
        "pull_output": pull_output,
        "externals_updated": {
            source_id: {
                "commit": source_ref.commit,
                "checkout_path": str(source_ref.checkout_path),
                "trust_status": source_ref.trust_status,
            }
            for source_id, source_ref in sorted(refreshed_sources.items())
        },
        "tool_dirs_touched": reseed_summary["global_written"],
        "workspaces_refreshed": reseed_summary["workspaces"],
        "stale_removed": reseed_summary["stale_removed"],
    }
    write_json(update_log_path(machine_config), payload)
    return payload
