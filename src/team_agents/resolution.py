from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path

from team_agents.activation import apply_enabled_override, select_activations
from team_agents.errors import ResolutionError, ValidationError
from team_agents.git_tools import find_git_root, list_normalized_remotes
from team_agents.models import (
    CorpRepo,
    Item,
    ItemOverride,
    LayerData,
    MachineConfig,
    ResolutionResult,
    ResolvedItem,
    SourceRef,
    UserLayer,
    WorkspaceBinding,
    WorkspaceContext,
)
from team_agents.sources import load_source_items, materialize_source


def build_workspace_context(workspace: Path, corp: CorpRepo, user: UserLayer) -> WorkspaceContext:
    workspace = workspace.resolve()
    git_root = find_git_root(workspace)
    if git_root is None:
        binding = match_workspace_binding(workspace, user.workspace_bindings)
        context = WorkspaceContext(
            workspace=workspace,
            git_root=None,
            normalized_remotes=[],
            is_non_git=True,
            is_unknown=binding is None,
            binding_name=binding.name if binding else None,
        )
        if binding:
            apply_binding(context, binding, corp)
        return context
    remotes = list_normalized_remotes(git_root)
    matching = [
        repo_id
        for repo_id, layer in corp.repos.items()
        if set(remotes).intersection(layer.config.normalized_remotes)
    ]
    if len(matching) > 1:
        raise ResolutionError(f"Multiple repo mappings matched remotes for {git_root}: {', '.join(sorted(matching))}")
    if not matching:
        binding = match_workspace_binding(git_root, user.workspace_bindings)
        context = WorkspaceContext(
            workspace=workspace,
            git_root=git_root,
            normalized_remotes=remotes,
            is_unknown=binding is None,
            binding_name=binding.name if binding else None,
        )
        if binding:
            apply_binding(context, binding, corp)
        return context
    repo_id = matching[0]
    repo_layer = corp.repos[repo_id]
    return WorkspaceContext(
        workspace=workspace,
        git_root=git_root,
        normalized_remotes=remotes,
        matched_repo_id=repo_id,
        matched_repo_group_id=repo_layer.config.repo_group_id,
        repo_class=repo_layer.config.repo_class or "internal",
    )


def resolve_workspace(
    workspace: Path,
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserLayer,
    profile: str | None = None,
) -> ResolutionResult:
    context = build_workspace_context(workspace, corp, user)
    if profile:
        context.profile = profile
    layers = select_layers(context, corp, user)
    profile_layers = select_profile_layers(context, layers)
    activation_layers = activation_layer_order(layers, profile_layers)
    enabled_sources = merge_sources(layers)
    resolved_items, source_details = gather_items(layers, enabled_sources, machine_config, corp, user)
    activation = select_activations(
        activation_layers=activation_layers,
        resolved_items=resolved_items,
        org_config=corp.org.config,
        user_config=user.layer.config,
        is_unknown_workspace=context.is_unknown,
        binding_disabled_skills=context.binding_disabled_skills,
    )
    active_items: dict[str, ResolvedItem] = {}
    denied_items: dict[str, ResolvedItem] = {}
    warnings: list[str] = []
    for item_id in activation.active_ids:
        resolved = resolved_items.get(item_id)
        if resolved is None:
            raise ResolutionError(f"Missing referenced item: {item_id}")
        apply_enabled_override(resolved, activation_layers)
        if not resolved.active:
            resolved.activated_by = activation.activation_map.get(item_id, [])
            resolved.activation_reason = activation.activation_reasons.get(item_id)
            denied_items[item_id] = resolved
            continue
        denial = evaluate_item_eligibility(
            context,
            resolved,
            item_id in activation.required_item_ids,
        )
        if denial:
            resolved.denied_reason = denial
            resolved.activated_by = activation.activation_map.get(item_id, [])
            resolved.activation_reason = activation.activation_reasons.get(item_id)
            denied_items[item_id] = resolved
            raise ResolutionError(f"{item_id} is not allowed in this workspace: {denial}")
        resolved.activated_by = activation.activation_map.get(item_id, [])
        resolved.activation_reason = activation.activation_reasons.get(item_id)
        active_items[item_id] = resolved
    for item_id, resolved in resolved_items.items():
        if item_id not in activation.active_ids and resolved.denied_reason:
            denied_items[item_id] = resolved
    if any(
        override.item_id in set(corp.org.config.baseline_policies + corp.org.config.required_completion_gates + corp.org.config.required_packs)
        and override.enabled is False
        for override in user.layer.config.item_overrides
    ):
        raise ResolutionError("User layers may not disable required policies, completion gates, or packs")
    if any(
        field in user.layer.config.protected_fields
        for field in corp.org.config.protected_fields
    ):
        warnings.append("User protected field overlap ignored")
    warnings.extend(evaluate_compatibility_warnings(active_items, activation_layers))
    layer_chain = [layer.config.layer_name for layer in activation_layers]
    return ResolutionResult(
        workspace_context=context,
        layer_chain=layer_chain,
        applied_layers=[
            {"layer_name": layer.config.layer_name, "identifier": layer.config.identifier}
            for layer in activation_layers
        ],
        enabled_sources=enabled_sources,
        source_details=source_details,
        enabled_skills=sorted(item_id for item_id in activation.enabled_skills if item_id in active_items),
        active_policies=sorted(item_id for item_id in activation.active_policy_ids if item_id in active_items),
        active_contexts=sorted(item_id for item_id in activation.active_context_ids if item_id in active_items),
        active_completion_gates=sorted(item_id for item_id in activation.active_completion_gate_ids if item_id in active_items),
        active_packs=sorted(item_id for item_id in activation.active_pack_ids if item_id in active_items),
        active_playbooks=sorted(item_id for item_id in activation.active_playbook_ids if item_id in active_items),
        active_profiles=sorted(item_id for item_id in activation.active_profile_ids if item_id in active_items),
        recommended_items=sorted(
            item_id for item_id in activation.recommended_item_ids if item_id in resolved_items and item_id not in active_items
        ),
        recommended_agent_types=activation.recommended_agent_types,
        items=active_items,
        denied_items=denied_items,
        warnings=warnings,
        selected_profile_configs=[layer.config for layer in profile_layers],
    )


def resolve_user_global(
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserLayer,
) -> ResolutionResult:
    context = WorkspaceContext(
        workspace=user.root,
        git_root=None,
        normalized_remotes=[],
        repo_class="internal",
        is_unknown=False,
        is_non_git=True,
    )
    layers = [corp.org, user.layer]
    activation_layers = layers
    enabled_sources = merge_sources(layers)
    resolved_items, source_details = gather_items(layers, enabled_sources, machine_config, corp, user)
    activation = select_activations(
        activation_layers=activation_layers,
        resolved_items=resolved_items,
        org_config=corp.org.config,
        user_config=user.layer.config,
        is_unknown_workspace=False,
    )
    active_items: dict[str, ResolvedItem] = {}
    denied_items: dict[str, ResolvedItem] = {}
    for item_id in activation.active_ids:
        resolved = resolved_items.get(item_id)
        if resolved is None:
            raise ResolutionError(f"Missing referenced item: {item_id}")
        apply_enabled_override(resolved, activation_layers)
        resolved.activated_by = activation.activation_map.get(item_id, [])
        resolved.activation_reason = activation.activation_reasons.get(item_id)
        if resolved.active:
            active_items[item_id] = resolved
        else:
            denied_items[item_id] = resolved
    if any(
        override.item_id in set(corp.org.config.baseline_policies + corp.org.config.required_completion_gates + corp.org.config.required_packs)
        and override.enabled is False
        for override in user.layer.config.item_overrides
    ):
        raise ResolutionError("User layers may not disable required policies, completion gates, or packs")
    return ResolutionResult(
        workspace_context=context,
        layer_chain=[layer.config.layer_name for layer in activation_layers],
        applied_layers=[
            {"layer_name": layer.config.layer_name, "identifier": layer.config.identifier}
            for layer in activation_layers
        ],
        enabled_sources=enabled_sources,
        source_details=source_details,
        enabled_skills=sorted(item_id for item_id in activation.enabled_skills if item_id in active_items),
        active_policies=sorted(item_id for item_id in activation.active_policy_ids if item_id in active_items),
        active_contexts=sorted(item_id for item_id in activation.active_context_ids if item_id in active_items),
        active_completion_gates=sorted(item_id for item_id in activation.active_completion_gate_ids if item_id in active_items),
        active_packs=sorted(item_id for item_id in activation.active_pack_ids if item_id in active_items),
        active_playbooks=sorted(item_id for item_id in activation.active_playbook_ids if item_id in active_items),
        active_profiles=sorted(item_id for item_id in activation.active_profile_ids if item_id in active_items),
        recommended_items=sorted(
            item_id for item_id in activation.recommended_item_ids if item_id in resolved_items and item_id not in active_items
        ),
        recommended_agent_types=activation.recommended_agent_types,
        items=active_items,
        denied_items=denied_items,
        warnings=evaluate_compatibility_warnings(active_items, activation_layers),
    )


def evaluate_compatibility_warnings(active_items: dict[str, ResolvedItem], layers: list[LayerData]) -> list[str]:
    languages = set(merge_context_list(layers, "languages"))
    frameworks = set(merge_context_list(layers, "frameworks"))
    repo_tags = set(merge_context_list(layers, "repo_tags"))
    framework_versions = merge_context_dict(layers, "framework_versions")
    warnings: list[str] = []
    for item_id, resolved in sorted(active_items.items()):
        item = resolved.item
        item_languages = set(item.applies_to_languages)
        if languages and item_languages and languages.isdisjoint(item_languages):
            warnings.append(
                f"compatibility mismatch for {item_id}: applies_to_languages={sorted(item_languages)} workspace_languages={sorted(languages)}"
            )
        item_frameworks = set(item.applies_to_frameworks)
        if frameworks and item_frameworks and frameworks.isdisjoint(item_frameworks):
            warnings.append(
                f"compatibility mismatch for {item_id}: applies_to_frameworks={sorted(item_frameworks)} workspace_frameworks={sorted(frameworks)}"
            )
        item_repo_tags = set(item.repo_tags)
        if repo_tags and item_repo_tags and repo_tags.isdisjoint(item_repo_tags):
            warnings.append(
                f"compatibility mismatch for {item_id}: repo_tags={sorted(item_repo_tags)} workspace_repo_tags={sorted(repo_tags)}"
            )
        for framework, constraint in sorted(item.compatible_versions.items()):
            actual = framework_versions.get(framework)
            if actual and not version_satisfies(actual, constraint):
                warnings.append(
                    f"compatibility mismatch for {item_id}: {framework} version {actual} does not satisfy {constraint}"
                )
    return warnings


def merge_context_list(layers: list[LayerData], field: str) -> list[str]:
    values: list[str] = []
    for layer in layers:
        for value in getattr(layer.config, field):
            if value not in values:
                values.append(value)
    return values


def merge_context_dict(layers: list[LayerData], field: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for layer in layers:
        values.update(getattr(layer.config, field))
    return values


def version_satisfies(actual: str, constraint: str) -> bool:
    for part in [item.strip() for item in constraint.split(",") if item.strip()]:
        match = re.fullmatch(r"(>=|<=|>|<|==)?\s*([0-9][0-9A-Za-z_.-]*)", part)
        if not match:
            return True
        operator = match.group(1) or "=="
        expected = match.group(2)
        comparison = compare_versions(actual, expected)
        if operator == ">=" and comparison < 0:
            return False
        if operator == ">" and comparison <= 0:
            return False
        if operator == "<=" and comparison > 0:
            return False
        if operator == "<" and comparison >= 0:
            return False
        if operator == "==" and comparison != 0:
            return False
    return True


def compare_versions(left: str, right: str) -> int:
    left_parts = version_parts(left)
    right_parts = version_parts(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


def version_parts(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value)) or (0,)


def select_layers(context: WorkspaceContext, corp: CorpRepo, user: UserLayer) -> list[LayerData]:
    layers = [corp.org]
    if context.matched_repo_group_id:
        repo_group = corp.repo_groups.get(context.matched_repo_group_id)
        if repo_group is None:
            raise ResolutionError(f"Repo-group {context.matched_repo_group_id} not found")
        layers.append(repo_group)
    if context.matched_repo_id:
        repo = corp.repos.get(context.matched_repo_id)
        if repo is None:
            raise ResolutionError(f"Repo {context.matched_repo_id} not found")
        layers.append(repo)
    layers.append(user.layer)
    return layers


def activation_layer_order(layers: list[LayerData], profile_layers: list[LayerData]) -> list[LayerData]:
    if not profile_layers:
        return layers
    user_layers = [layer for layer in layers if layer.config.layer_name == "user"]
    base_layers = [layer for layer in layers if layer.config.layer_name != "user"]
    return base_layers + profile_layers + user_layers


def select_profile_layers(context: WorkspaceContext, layers: list[LayerData]) -> list[LayerData]:
    requested = context.profile or os.environ.get("TEAM_AGENTS_PROFILE")
    if not requested:
        for layer in reversed(layers):
            if layer.config.default_profile:
                requested = layer.config.default_profile
                break
    if not requested:
        return []
    allowed: list[str] = []
    for layer in layers:
        for profile_id in layer.config.allowed_profiles:
            if profile_id not in allowed:
                allowed.append(profile_id)
    if allowed and requested not in allowed:
        raise ResolutionError(f"Profile {requested!r} is not allowed for this workspace")
    profile_layers: list[LayerData] = []
    for layer in layers:
        profile = layer.profiles.get(requested)
        if profile is not None:
            profile_layers.append(LayerData(config=profile, items={}))
    if profile_layers:
        context.profile = requested
        return profile_layers
    raise ResolutionError(f"Profile {requested!r} was selected but no profile definition was found")


def merge_sources(layers: list[LayerData]) -> list[str]:
    enabled: list[str] = []
    disabled: set[str] = set()
    for layer in layers:
        for source_id in layer.config.enabled_sources:
            if source_id not in enabled:
                enabled.append(source_id)
        disabled.update(layer.config.disabled_sources)
    return [source_id for source_id in enabled if source_id not in disabled]


def gather_items(
    layers: list[LayerData],
    enabled_sources: list[str],
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserLayer,
) -> tuple[dict[str, ResolvedItem], dict[str, SourceRef]]:
    layered_items: dict[str, ResolvedItem] = {}
    source_details: dict[str, SourceRef] = {}
    source_map = {**corp.sources, **user.personal_sources}
    for source_id in enabled_sources:
        source = source_map.get(source_id)
        if source is None:
            raise ResolutionError(f"Unknown source reference: {source_id}")
        source_ref = materialize_source(source, machine_config)
        source_details[source_id] = source_ref
        source_items = load_source_items(source, source_ref)
        for item_id, item in source_items.items():
            layered_items[item_id] = ResolvedItem(item=item, layer_name=f"source:{source_id}", status="direct")
    for layer in layers:
        for item_id, item in layer.items.items():
            if item_id in layered_items:
                replaced = layered_items[item_id]
                validate_layer_replacement(layer, replaced, item, corp)
                layered_items[item_id] = ResolvedItem(
                    item=deepcopy(item),
                    layer_name=layer.config.layer_name,
                    status="replaced",
                    replaced_from={
                        "id": replaced.item.item_id,
                        "source_type": replaced.item.source_type,
                        "source_namespace": replaced.item.source_namespace,
                        "source_ref": replaced.item.source_ref,
                    },
                )
            else:
                layered_items[item_id] = ResolvedItem(item=deepcopy(item), layer_name=layer.config.layer_name, status="direct")
        for override in layer.config.item_overrides:
            resolved = layered_items.get(override.item_id)
            if resolved is None:
                raise ResolutionError(f"Item override references unknown id {override.item_id}")
            apply_field_override(resolved, override, layer.config.layer_name)
    return layered_items, source_details


def apply_field_override(resolved: ResolvedItem, override: ItemOverride, layer_name: str) -> None:
    if override.timeout_seconds is not None:
        resolved.item.timeout_seconds = override.timeout_seconds
    if override.recommended_agent_types is not None:
        resolved.item.recommended_agent_types = override.recommended_agent_types
    if override.tags is not None:
        resolved.item.tags = override.tags
    if override.source_note is not None:
        resolved.item.source_note = override.source_note
    if override.enabled is False:
        resolved.active = False
    if override.enabled is True:
        resolved.active = True
    if resolved.status == "direct":
        resolved.status = "field-overridden"
    resolved.overridden_by.append(layer_name)


def evaluate_item_eligibility(context: WorkspaceContext, resolved: ResolvedItem, is_baseline_policy: bool) -> str | None:
    if context.repo_class == "client" and resolved.item.privacy == "corp-private":
        return "corp-private material cannot be written into client repo output"
    if is_baseline_policy and not resolved.active:
        return "required items are protected"
    return None


def validate_layer_replacement(layer: LayerData, replaced: ResolvedItem, replacement: Item, corp: CorpRepo) -> None:
    if layer.config.layer_name != "user":
        return
    org_required = set(corp.org.config.baseline_policies + corp.org.config.required_completion_gates + corp.org.config.required_packs)
    if replaced.item.item_id in org_required:
        raise ResolutionError(f"User layer may not replace required item {replaced.item.item_id}")
    if privacy_rank(replacement.privacy) < privacy_rank(replaced.item.privacy):
        raise ResolutionError(f"User layer may not weaken privacy for {replaced.item.item_id}")


def privacy_rank(privacy: str) -> int:
    return {"repo-safe": 0, "corp-private": 1}[privacy]


def match_workspace_binding(path: Path, bindings: list[WorkspaceBinding]) -> WorkspaceBinding | None:
    candidates = []
    for binding in bindings:
        try:
            path.relative_to(binding.path)
        except ValueError:
            continue
        candidates.append(binding)
    if not candidates:
        return None
    candidates.sort(key=lambda binding: len(str(binding.path)), reverse=True)
    return candidates[0]


def apply_binding(context: WorkspaceContext, binding: WorkspaceBinding, corp: CorpRepo) -> None:
    if binding.repo_id:
        repo = corp.repos.get(binding.repo_id)
        if repo is None:
            raise ValidationError(f"Workspace binding references unknown repo {binding.repo_id}")
        context.matched_repo_id = binding.repo_id
        context.matched_repo_group_id = repo.config.repo_group_id
        context.repo_class = repo.config.repo_class or "internal"
        context.is_unknown = False
    elif binding.repo_group_id:
        if binding.repo_group_id not in corp.repo_groups:
            raise ValidationError(f"Workspace binding references unknown repo-group {binding.repo_group_id}")
        context.matched_repo_group_id = binding.repo_group_id
        context.repo_class = "internal"
        context.is_unknown = False
    context.profile = binding.profile
    context.binding_disabled_skills = list(binding.disabled_skills)
