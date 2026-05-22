from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Callable, TypedDict

from team_agents.errors import TeamAgentsError
from team_agents.models import CorpRepo, Item, LayerConfig, LayerData, MachineConfig, ResolutionResult, ResolvedItem, UserLayer
from team_agents.resolution import resolve_workspace

class CollisionItem(TypedDict):
    item_id: str
    title: str
    targets: list[str]


class SkillCollision(TypedDict):
    slug: str
    items: list[CollisionItem]


def unique_list(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def merge_delta_values(base: list[str], additions: list[str] | None, removals: list[str] | None) -> list[str]:
    values = list(base)
    for value in additions or []:
        if value not in values:
            values.append(value)
    if removals:
        values = [value for value in values if value not in removals]
    return values


def validate_repo_group_id(repo_group_id: str | None, corp: CorpRepo) -> None:
    if repo_group_id and repo_group_id not in corp.repo_groups:
        raise TeamAgentsError(f"Unknown repo-group id: {repo_group_id}")


def resolve_repo_collisions(
    *,
    json_mode: bool,
    prompt_losers: Callable[[list[SkillCollision]], list[str]],
    workspace: Path,
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserLayer,
    repo_id: str,
    repo_class: str,
    repo_group_id: str | None,
    normalized_remotes: list[str],
    enabled_skills: list[str],
    disabled_skills: list[str],
    enabled_sources: list[str],
    disabled_sources: list[str],
    mode: str,
) -> tuple[list[str], list[str]]:
    while True:
        simulated = simulate_repo_resolution(
            workspace=workspace,
            machine_config=machine_config,
            corp=corp,
            user=user,
            repo_id=repo_id,
            repo_class=repo_class,
            repo_group_id=repo_group_id,
            normalized_remotes=normalized_remotes,
            enabled_skills=enabled_skills,
            disabled_skills=disabled_skills,
            enabled_sources=enabled_sources,
            disabled_sources=disabled_sources,
            mode=mode,
        )
        collisions = detect_skill_collisions(simulated)
        if not collisions:
            return enabled_skills, disabled_skills
        if json_mode:
            raise TeamAgentsError(format_collision_error(collisions))
        losers = prompt_losers(collisions)
        disabled_skills = merge_delta_values(disabled_skills, losers, None)
        enabled_skills = [item_id for item_id in enabled_skills if item_id not in losers]


def resolve_group_collisions(
    *,
    json_mode: bool,
    prompt_losers: Callable[[list[SkillCollision]], list[str]],
    workspace: Path,
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserLayer,
    repo_id: str,
    group_id: str,
    enabled_skills: list[str],
    disabled_skills: list[str],
    enabled_sources: list[str],
    disabled_sources: list[str],
    mode: str,
) -> tuple[list[str], list[str]]:
    while True:
        simulated = simulate_group_resolution(
            workspace=workspace,
            machine_config=machine_config,
            corp=corp,
            user=user,
            repo_id=repo_id,
            group_id=group_id,
            enabled_skills=enabled_skills,
            disabled_skills=disabled_skills,
            enabled_sources=enabled_sources,
            disabled_sources=disabled_sources,
            mode=mode,
        )
        collisions = detect_skill_collisions(simulated)
        if not collisions:
            return enabled_skills, disabled_skills
        if json_mode:
            raise TeamAgentsError(format_collision_error(collisions))
        losers = prompt_losers(collisions)
        disabled_skills = merge_delta_values(disabled_skills, losers, None)
        enabled_skills = [item_id for item_id in enabled_skills if item_id not in losers]


def simulate_repo_resolution(
    *,
    workspace: Path,
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserLayer,
    repo_id: str,
    repo_class: str,
    repo_group_id: str | None,
    normalized_remotes: list[str],
    enabled_skills: list[str],
    disabled_skills: list[str],
    enabled_sources: list[str],
    disabled_sources: list[str],
    mode: str,
) -> ResolutionResult:
    corp_candidate = deepcopy(corp)
    if mode == "created":
        corp_candidate.repos[repo_id] = LayerData(
            config=LayerConfig(
                layer_name="repo",
                layer_path=machine_config.corp_repo_path / "repos" / repo_id,
                identifier=repo_id,
                enabled_sources=list(enabled_sources),
                disabled_sources=list(disabled_sources),
                enabled_skills=list(enabled_skills),
                disabled_skills=list(disabled_skills),
                normalized_remotes=list(normalized_remotes),
                repo_group_id=repo_group_id,
                repo_class=repo_class,
            ),
            items={},
        )
    else:
        config = corp_candidate.repos[repo_id].config
        config.repo_class = repo_class
        config.repo_group_id = repo_group_id
        config.normalized_remotes = list(normalized_remotes)
        config.enabled_skills = list(enabled_skills)
        config.disabled_skills = list(disabled_skills)
        config.enabled_sources = list(enabled_sources)
        config.disabled_sources = list(disabled_sources)
    return resolve_workspace(workspace, machine_config, corp_candidate, user)


def simulate_group_resolution(
    *,
    workspace: Path,
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserLayer,
    repo_id: str,
    group_id: str,
    enabled_skills: list[str],
    disabled_skills: list[str],
    enabled_sources: list[str],
    disabled_sources: list[str],
    mode: str,
) -> ResolutionResult:
    corp_candidate = deepcopy(corp)
    if mode == "created":
        corp_candidate.repo_groups[group_id] = LayerData(
            config=LayerConfig(
                layer_name="repo-group",
                layer_path=machine_config.corp_repo_path / "repo-groups" / group_id,
                identifier=group_id,
                enabled_sources=list(enabled_sources),
                disabled_sources=list(disabled_sources),
                enabled_skills=list(enabled_skills),
                disabled_skills=list(disabled_skills),
            ),
            items={},
        )
    else:
        config = corp_candidate.repo_groups[group_id].config
        config.enabled_skills = list(enabled_skills)
        config.disabled_skills = list(disabled_skills)
        config.enabled_sources = list(enabled_sources)
        config.disabled_sources = list(disabled_sources)
    corp_candidate.repos[repo_id].config.repo_group_id = group_id
    return resolve_workspace(workspace, machine_config, corp_candidate, user)


def detect_skill_collisions(result: ResolutionResult) -> list[SkillCollision]:
    by_slug: dict[str, list[ResolvedItem]] = {}
    for resolved in result.items.values():
        if resolved.item.kind != "skill" or not resolved.active:
            continue
        by_slug.setdefault(resolved.item.slug, []).append(resolved)
    collisions: list[SkillCollision] = []
    for slug, resolved_items in sorted(by_slug.items()):
        if len(resolved_items) < 2:
            continue
        overlapping_groups: list[list[ResolvedItem]] = []
        remaining = list(resolved_items)
        while remaining:
            current = [remaining.pop(0)]
            current_tools = normalized_tool_targets(current[0].item)
            changed = True
            while changed:
                changed = False
                next_remaining = []
                for candidate in remaining:
                    candidate_tools = normalized_tool_targets(candidate.item)
                    if tool_overlap(current_tools, candidate_tools):
                        current.append(candidate)
                        current_tools |= candidate_tools
                        changed = True
                    else:
                        next_remaining.append(candidate)
                remaining = next_remaining
            overlapping_groups.append(current)
        for group in overlapping_groups:
            if len(group) < 2:
                continue
            collisions.append(
                {
                    "slug": slug,
                    "items": [
                        {
                            "item_id": resolved.item.item_id,
                            "title": resolved.item.title,
                            "targets": sorted(normalized_tool_targets(resolved.item)),
                        }
                        for resolved in sorted(group, key=lambda value: value.item.item_id)
                    ],
                }
            )
    return collisions


def normalized_tool_targets(item: Item) -> set[str]:
    known = {"claude", "codex", "cursor"}
    if not item.target_tools:
        return set(known)
    return {tool for tool in item.target_tools if tool in known}


def tool_overlap(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    return bool(left.intersection(right))


def format_collision_error(collisions: list[SkillCollision]) -> str:
    parts = []
    for collision in collisions:
        items = ", ".join(
            f"{item['item_id']}[{','.join(item['targets']) or 'none'}]"
            for item in collision["items"]
        )
        parts.append(f"slug {collision['slug']}: {items}")
    return (
        "Skill emission collisions must be resolved before apply: "
        + "; ".join(parts)
        + ". Disable one of the colliding skills at repo scope."
    )


def effective_standard_state(resolution: ResolutionResult) -> dict[str, object]:
    return {
        "enabled_skills": resolution.enabled_skills,
        "enabled_sources": resolution.enabled_sources,
        "optional_policies": resolution.active_policies,
        "contexts": resolution.active_contexts,
        "recommended_agent_types": resolution.recommended_agent_types,
    }


def layer_local_deltas(layer: LayerConfig) -> dict[str, object]:
    return {
        "enabled_skills": list(layer.enabled_skills),
        "disabled_skills": list(layer.disabled_skills),
        "enabled_sources": list(layer.enabled_sources),
        "disabled_sources": list(layer.disabled_sources),
        "optional_policies": list(layer.optional_policies),
        "disabled_optional_policies": list(layer.disabled_optional_policies),
        "contexts": list(layer.contexts),
        "recommended_agent_types": list(layer.recommended_agent_types),
    }
