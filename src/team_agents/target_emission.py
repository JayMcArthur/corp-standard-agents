from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from team_agents.errors import ResolutionError
from team_agents.models import Item, MachineConfig, ResolutionResult

TARGETS = ("codex", "claude", "cursor")
ROUTER_TARGETS = {
    "codex": "AGENTS.md",
    "claude": "CLAUDE.md",
    "cursor": ".cursor/rules/team-agents.mdc",
}
ROUTER_FILES = tuple(ROUTER_TARGETS.values())


@dataclass(slots=True)
class TargetEmissionPlan:
    targets: list[str]
    repo_class: str
    workspace_root: Path | None = None


def build_workspace_emission_plan(result: ResolutionResult, machine_config: MachineConfig) -> TargetEmissionPlan:
    return TargetEmissionPlan(
        targets=resolve_tool_targets(machine_config.default_tool_target),
        repo_class=result.workspace_context.repo_class or "internal",
        workspace_root=result.workspace_context.git_root or result.workspace_context.workspace,
    )


def build_user_global_emission_plan(machine_config: MachineConfig) -> TargetEmissionPlan:
    return TargetEmissionPlan(
        targets=resolve_tool_targets(machine_config.default_tool_target),
        repo_class="internal",
    )


def resolve_tool_targets(default_tool_target: str) -> list[str]:
    if default_tool_target == "all":
        return list(TARGETS)
    if default_tool_target in TARGETS:
        return [default_tool_target]
    raise ResolutionError(f"Unsupported tool target {default_tool_target!r}")


def target_included(item: Item, target: str) -> bool:
    settings = item.target_settings.get(target)
    if settings is not None:
        return settings.include
    return not item.target_tools or target in item.target_tools
