from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path

from team_agents.errors import ResolutionError, ValidationError
from team_agents.git_tools import find_git_root, list_normalized_remotes
from team_agents.models import (
    CorpRepo,
    Item,
    ItemOverride,
    LayerConfig,
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
from team_agents.validation import validate_canonical_id


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
    enabled_skills, skill_activations = merge_set_fields(activation_layers, "enabled_skills", "disabled_skills")
    optional_policies, policy_activations = merge_set_fields(activation_layers, "optional_policies", "disabled_optional_policies")
    contexts, context_activations = merge_set_fields(activation_layers, "contexts", "disabled_contexts")
    optional_completion_gates, completion_gate_activations = merge_set_fields(
        activation_layers, "optional_completion_gates", "disabled_optional_completion_gates"
    )
    enabled_packs, pack_activations = merge_set_fields(activation_layers, "enabled_packs", "disabled_packs")
    enabled_playbooks, playbook_activations = merge_set_fields(activation_layers, "enabled_playbooks", "disabled_playbooks")
    enabled_profiles, profile_activations = merge_set_fields(activation_layers, "enabled_profiles", "disabled_profiles")
    baseline_policies = list(dict.fromkeys(corp.org.config.baseline_policies))
    baseline_policy_activations = {item_id: [layer_ref(corp.org.config)] for item_id in baseline_policies}
    required_completion_gates = merge_required_field(activation_layers, "required_completion_gates")
    required_completion_gate_activations = activation_map_for_required(activation_layers, "required_completion_gates")
    required_packs = merge_required_field(activation_layers, "required_packs")
    required_pack_activations = activation_map_for_required(activation_layers, "required_packs")
    if context.is_unknown:
        user_layer = user.layer.config
        enabled_skills = (set(corp.org.config.minimal_enabled_skills) | set(user_layer.enabled_skills)) - set(user_layer.disabled_skills)
        optional_policies = (set(corp.org.config.minimal_optional_policies) | set(user_layer.optional_policies)) - set(
            user_layer.disabled_optional_policies
        )
        contexts = (set(corp.org.config.minimal_contexts) | set(user_layer.contexts)) - set(user_layer.disabled_contexts)
        optional_completion_gates = set(user_layer.optional_completion_gates) - set(user_layer.disabled_optional_completion_gates)
        enabled_packs = set(user_layer.enabled_packs) - set(user_layer.disabled_packs)
        enabled_playbooks = set(user_layer.enabled_playbooks) - set(user_layer.disabled_playbooks)
        enabled_profiles = set(user_layer.enabled_profiles) - set(user_layer.disabled_profiles)
        skill_activations = activation_map_for_unknown(
            corp.org.config.minimal_enabled_skills,
            user_layer.enabled_skills,
            user_layer.disabled_skills,
            corp.org.config,
            user_layer,
        )
        policy_activations = activation_map_for_unknown(
            corp.org.config.minimal_optional_policies,
            user_layer.optional_policies,
            user_layer.disabled_optional_policies,
            corp.org.config,
            user_layer,
        )
        context_activations = activation_map_for_unknown(
            corp.org.config.minimal_contexts,
            user_layer.contexts,
            user_layer.disabled_contexts,
            corp.org.config,
            user_layer,
        )
        completion_gate_activations = activation_map_for_unknown(
            [],
            user_layer.optional_completion_gates,
            user_layer.disabled_optional_completion_gates,
            corp.org.config,
            user_layer,
        )
        pack_activations = activation_map_for_unknown(
            [],
            user_layer.enabled_packs,
            user_layer.disabled_packs,
            corp.org.config,
            user_layer,
        )
        playbook_activations = activation_map_for_unknown(
            [],
            user_layer.enabled_playbooks,
            user_layer.disabled_playbooks,
            corp.org.config,
            user_layer,
        )
        profile_activations = activation_map_for_unknown(
            [],
            user_layer.enabled_profiles,
            user_layer.disabled_profiles,
            corp.org.config,
            user_layer,
        )
    if context.binding_disabled_skills:
        enabled_skills = set(enabled_skills) - set(context.binding_disabled_skills)
        for item_id in list(skill_activations):
            if item_id in context.binding_disabled_skills:
                skill_activations.pop(item_id, None)
    active_policy_ids = baseline_policies + [item_id for item_id in optional_policies if item_id not in baseline_policies]
    active_completion_gate_ids = required_completion_gates + [
        item_id for item_id in optional_completion_gates if item_id not in required_completion_gates
    ]
    active_pack_ids = required_packs + [item_id for item_id in enabled_packs if item_id not in required_packs]
    pack_expansion_activations: dict[str, list[str]] = {}
    pack_required_items: set[str] = set()
    if active_pack_ids:
        pack_source_activations = merge_activation_maps(pack_activations, required_pack_activations)
        pack_expansion = expand_pack_contents(active_pack_ids, resolved_items, pack_source_activations)
        enabled_skills.update(pack_expansion["enabled_skills"])
        optional_policies.update(pack_expansion["optional_policies"])
        contexts.update(pack_expansion["contexts"])
        optional_completion_gates.update(pack_expansion["optional_completion_gates"])
        enabled_packs.update(pack_expansion["enabled_packs"])
        enabled_playbooks.update(pack_expansion["enabled_playbooks"])
        for item_id in pack_expansion["baseline_policies"]:
            if item_id not in active_policy_ids:
                active_policy_ids.append(item_id)
        for item_id in pack_expansion["required_completion_gates"]:
            if item_id not in active_completion_gate_ids:
                active_completion_gate_ids.append(item_id)
        for item_id in pack_expansion["required_packs"]:
            if item_id not in active_pack_ids:
                active_pack_ids.append(item_id)
        for item_id in pack_expansion["active_packs"]:
            if item_id not in active_pack_ids:
                active_pack_ids.append(item_id)
        pack_expansion_activations = pack_expansion["activations"]
        pack_required_items = set(pack_expansion["required_items"])
    for item_id in optional_policies:
        if item_id not in active_policy_ids:
            active_policy_ids.append(item_id)
    for item_id in optional_completion_gates:
        if item_id not in active_completion_gate_ids:
            active_completion_gate_ids.append(item_id)
    for item_id in enabled_packs:
        if item_id not in active_pack_ids:
            active_pack_ids.append(item_id)
    activation_reasons: dict[str, str] = {}
    for item_id in set(baseline_policies) | set(required_completion_gates) | set(required_packs) | pack_required_items:
        activation_reasons[item_id] = "required"
    for item_id in (
        set(enabled_skills)
        | set(optional_policies)
        | set(contexts)
        | set(optional_completion_gates)
        | set(enabled_packs)
        | set(enabled_playbooks)
        | set(enabled_profiles)
    ):
        activation_reasons.setdefault(item_id, "enabled")
    recommended_agent_types = merge_recommended_agent_types(activation_layers, unknown_only=context.is_unknown)
    recommended_items = merge_recommended_item_ids(activation_layers)
    active_ids = (
        set(enabled_skills)
        | set(active_policy_ids)
        | set(contexts)
        | set(active_completion_gate_ids)
        | set(active_pack_ids)
        | set(enabled_playbooks)
        | set(enabled_profiles)
    )
    activation_map: dict[str, list[str]] = {}
    for mapping in [
        skill_activations,
        policy_activations,
        context_activations,
        completion_gate_activations,
        pack_activations,
        playbook_activations,
        profile_activations,
        baseline_policy_activations,
        required_completion_gate_activations,
        required_pack_activations,
        pack_expansion_activations,
    ]:
        for item_id, refs in mapping.items():
            activation_map.setdefault(item_id, [])
            for ref in refs:
                if ref not in activation_map[item_id]:
                    activation_map[item_id].append(ref)
    active_items: dict[str, ResolvedItem] = {}
    denied_items: dict[str, ResolvedItem] = {}
    warnings: list[str] = []
    for item_id in active_ids:
        resolved = resolved_items.get(item_id)
        if resolved is None:
            raise ResolutionError(f"Missing referenced item: {item_id}")
        apply_enabled_override(resolved, activation_layers)
        if not resolved.active:
            resolved.activated_by = activation_map.get(item_id, [])
            resolved.activation_reason = activation_reasons.get(item_id)
            denied_items[item_id] = resolved
            continue
        denial = evaluate_item_eligibility(
            context,
            resolved,
            item_id in baseline_policies
            or item_id in required_completion_gates
            or item_id in required_packs
            or item_id in pack_required_items,
        )
        if denial:
            resolved.denied_reason = denial
            resolved.activated_by = activation_map.get(item_id, [])
            resolved.activation_reason = activation_reasons.get(item_id)
            denied_items[item_id] = resolved
            raise ResolutionError(f"{item_id} is not allowed in this workspace: {denial}")
            continue
        resolved.activated_by = activation_map.get(item_id, [])
        resolved.activation_reason = activation_reasons.get(item_id)
        active_items[item_id] = resolved
    for item_id, resolved in resolved_items.items():
        if item_id not in active_ids and resolved.denied_reason:
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
        enabled_skills=sorted(item_id for item_id in enabled_skills if item_id in active_items),
        active_policies=sorted(item_id for item_id in active_policy_ids if item_id in active_items),
        active_contexts=sorted(item_id for item_id in contexts if item_id in active_items),
        active_completion_gates=sorted(item_id for item_id in active_completion_gate_ids if item_id in active_items),
        active_packs=sorted(item_id for item_id in active_pack_ids if item_id in active_items),
        active_playbooks=sorted(item_id for item_id in enabled_playbooks if item_id in active_items),
        active_profiles=sorted(item_id for item_id in enabled_profiles if item_id in active_items),
        recommended_items=sorted(item_id for item_id in recommended_items if item_id in resolved_items and item_id not in active_items),
        recommended_agent_types=recommended_agent_types,
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
    enabled_skills, skill_activations = merge_set_fields(activation_layers, "enabled_skills", "disabled_skills")
    optional_policies, policy_activations = merge_set_fields(activation_layers, "optional_policies", "disabled_optional_policies")
    contexts, context_activations = merge_set_fields(activation_layers, "contexts", "disabled_contexts")
    optional_completion_gates, completion_gate_activations = merge_set_fields(
        activation_layers, "optional_completion_gates", "disabled_optional_completion_gates"
    )
    enabled_packs, pack_activations = merge_set_fields(activation_layers, "enabled_packs", "disabled_packs")
    enabled_playbooks, playbook_activations = merge_set_fields(activation_layers, "enabled_playbooks", "disabled_playbooks")
    enabled_profiles, profile_activations = merge_set_fields(activation_layers, "enabled_profiles", "disabled_profiles")
    baseline_policies = list(dict.fromkeys(corp.org.config.baseline_policies))
    baseline_policy_activations = {item_id: [layer_ref(corp.org.config)] for item_id in baseline_policies}
    required_completion_gates = merge_required_field(activation_layers, "required_completion_gates")
    required_completion_gate_activations = activation_map_for_required(activation_layers, "required_completion_gates")
    required_packs = merge_required_field(activation_layers, "required_packs")
    required_pack_activations = activation_map_for_required(activation_layers, "required_packs")
    active_policy_ids = baseline_policies + [item_id for item_id in optional_policies if item_id not in baseline_policies]
    active_completion_gate_ids = required_completion_gates + [
        item_id for item_id in optional_completion_gates if item_id not in required_completion_gates
    ]
    active_pack_ids = required_packs + [item_id for item_id in enabled_packs if item_id not in required_packs]
    pack_expansion_activations: dict[str, list[str]] = {}
    pack_required_items: set[str] = set()
    if active_pack_ids:
        pack_source_activations = merge_activation_maps(pack_activations, required_pack_activations)
        pack_expansion = expand_pack_contents(active_pack_ids, resolved_items, pack_source_activations)
        enabled_skills.update(pack_expansion["enabled_skills"])
        optional_policies.update(pack_expansion["optional_policies"])
        contexts.update(pack_expansion["contexts"])
        optional_completion_gates.update(pack_expansion["optional_completion_gates"])
        enabled_packs.update(pack_expansion["enabled_packs"])
        enabled_playbooks.update(pack_expansion["enabled_playbooks"])
        for item_id in pack_expansion["baseline_policies"]:
            if item_id not in active_policy_ids:
                active_policy_ids.append(item_id)
        for item_id in pack_expansion["required_completion_gates"]:
            if item_id not in active_completion_gate_ids:
                active_completion_gate_ids.append(item_id)
        for item_id in pack_expansion["required_packs"]:
            if item_id not in active_pack_ids:
                active_pack_ids.append(item_id)
        for item_id in pack_expansion["active_packs"]:
            if item_id not in active_pack_ids:
                active_pack_ids.append(item_id)
        pack_expansion_activations = pack_expansion["activations"]
        pack_required_items = set(pack_expansion["required_items"])
    for item_id in optional_policies:
        if item_id not in active_policy_ids:
            active_policy_ids.append(item_id)
    for item_id in optional_completion_gates:
        if item_id not in active_completion_gate_ids:
            active_completion_gate_ids.append(item_id)
    for item_id in enabled_packs:
        if item_id not in active_pack_ids:
            active_pack_ids.append(item_id)
    activation_reasons: dict[str, str] = {}
    for item_id in set(baseline_policies) | set(required_completion_gates) | set(required_packs) | pack_required_items:
        activation_reasons[item_id] = "required"
    for item_id in (
        set(enabled_skills)
        | set(optional_policies)
        | set(contexts)
        | set(optional_completion_gates)
        | set(enabled_packs)
        | set(enabled_playbooks)
        | set(enabled_profiles)
    ):
        activation_reasons.setdefault(item_id, "enabled")
    recommended_agent_types = merge_recommended_agent_types(activation_layers, unknown_only=False)
    recommended_items = merge_recommended_item_ids(activation_layers)
    active_ids = (
        set(enabled_skills)
        | set(active_policy_ids)
        | set(contexts)
        | set(active_completion_gate_ids)
        | set(active_pack_ids)
        | set(enabled_playbooks)
        | set(enabled_profiles)
    )
    activation_map: dict[str, list[str]] = {}
    for mapping in [
        skill_activations,
        policy_activations,
        context_activations,
        completion_gate_activations,
        pack_activations,
        playbook_activations,
        profile_activations,
        baseline_policy_activations,
        required_completion_gate_activations,
        required_pack_activations,
        pack_expansion_activations,
    ]:
        for item_id, refs in mapping.items():
            activation_map.setdefault(item_id, [])
            for ref in refs:
                if ref not in activation_map[item_id]:
                    activation_map[item_id].append(ref)
    active_items: dict[str, ResolvedItem] = {}
    denied_items: dict[str, ResolvedItem] = {}
    for item_id in active_ids:
        resolved = resolved_items.get(item_id)
        if resolved is None:
            raise ResolutionError(f"Missing referenced item: {item_id}")
        apply_enabled_override(resolved, activation_layers)
        resolved.activated_by = activation_map.get(item_id, [])
        resolved.activation_reason = activation_reasons.get(item_id)
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
        enabled_skills=sorted(item_id for item_id in enabled_skills if item_id in active_items),
        active_policies=sorted(item_id for item_id in active_policy_ids if item_id in active_items),
        active_contexts=sorted(item_id for item_id in contexts if item_id in active_items),
        active_completion_gates=sorted(item_id for item_id in active_completion_gate_ids if item_id in active_items),
        active_packs=sorted(item_id for item_id in active_pack_ids if item_id in active_items),
        active_playbooks=sorted(item_id for item_id in enabled_playbooks if item_id in active_items),
        active_profiles=sorted(item_id for item_id in enabled_profiles if item_id in active_items),
        recommended_items=sorted(item_id for item_id in recommended_items if item_id in resolved_items and item_id not in active_items),
        recommended_agent_types=recommended_agent_types,
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


def merge_set_fields(layers: list[LayerData], enabled_field: str, disabled_field: str) -> tuple[set[str], dict[str, list[str]]]:
    enabled: list[str] = []
    disabled: set[str] = set()
    activations: dict[str, list[str]] = {}
    for layer in layers:
        for item_id in getattr(layer.config, enabled_field):
            if item_id not in enabled:
                enabled.append(item_id)
            activations.setdefault(item_id, [])
            ref = layer_ref(layer.config)
            if ref not in activations[item_id]:
                activations[item_id].append(ref)
        disabled.update(getattr(layer.config, disabled_field))
    filtered = {item_id for item_id in enabled if item_id not in disabled}
    return filtered, {item_id: refs for item_id, refs in activations.items() if item_id in filtered}


def merge_required_field(layers: list[LayerData], field: str) -> list[str]:
    values: list[str] = []
    for layer in layers:
        for item_id in getattr(layer.config, field):
            if item_id not in values:
                values.append(item_id)
    return values


def activation_map_for_required(layers: list[LayerData], field: str) -> dict[str, list[str]]:
    activations: dict[str, list[str]] = {}
    for layer in layers:
        ref = layer_ref(layer.config)
        for item_id in getattr(layer.config, field):
            activations.setdefault(item_id, [])
            if ref not in activations[item_id]:
                activations[item_id].append(ref)
    return activations


def merge_activation_maps(*maps: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for mapping in maps:
        for item_id, refs in mapping.items():
            merged.setdefault(item_id, [])
            for ref in refs:
                if ref not in merged[item_id]:
                    merged[item_id].append(ref)
    return merged


def expand_pack_contents(
    initial_pack_ids: list[str],
    resolved_items: dict[str, ResolvedItem],
    pack_source_activations: dict[str, list[str]],
) -> dict[str, object]:
    expanded: dict[str, object] = {
        "enabled_skills": set(),
        "baseline_policies": set(),
        "optional_policies": set(),
        "contexts": set(),
        "required_completion_gates": set(),
        "optional_completion_gates": set(),
        "required_packs": set(),
        "enabled_packs": set(),
        "enabled_playbooks": set(),
        "active_packs": set(initial_pack_ids),
        "required_items": set(),
        "activations": {},
    }
    visiting: list[str] = []
    visited: set[str] = set()

    def add_activation(item_id: str, refs: list[str]) -> None:
        activations = expanded["activations"]
        assert isinstance(activations, dict)
        activations.setdefault(item_id, [])
        for ref in refs:
            if ref not in activations[item_id]:
                activations[item_id].append(ref)

    def refs_for_pack(pack_id: str) -> list[str]:
        refs = list(pack_source_activations.get(pack_id, []))
        pack_ref = f"pack:{pack_id}"
        if pack_ref not in refs:
            refs.append(pack_ref)
        return refs

    def activate_reference(pack_id: str, item_id: str, mode: str) -> None:
        _, _, kind, _ = validate_canonical_id(item_id)
        if kind == "profile":
            raise ResolutionError(f"Pack {pack_id} cannot activate profile item {item_id}")
        if mode == "required" and kind not in {"policy", "completion_gate", "pack"}:
            raise ResolutionError(f"Pack {pack_id} cannot require {kind} item {item_id}")
        field_by_kind = {
            "skill": "enabled_skills",
            "policy": "baseline_policies" if mode == "required" else "optional_policies",
            "context": "contexts",
            "completion_gate": "required_completion_gates" if mode == "required" else "optional_completion_gates",
            "pack": "required_packs" if mode == "required" else "enabled_packs",
            "playbook": "enabled_playbooks",
        }
        field = field_by_kind[kind]
        target = expanded[field]
        assert isinstance(target, set)
        target.add(item_id)
        if mode == "required":
            required_items = expanded["required_items"]
            assert isinstance(required_items, set)
            required_items.add(item_id)
        refs = refs_for_pack(pack_id)
        add_activation(item_id, refs)
        if kind == "pack":
            active_packs = expanded["active_packs"]
            assert isinstance(active_packs, set)
            active_packs.add(item_id)
            pack_source_activations.setdefault(item_id, [])
            for ref in refs:
                if ref not in pack_source_activations[item_id]:
                    pack_source_activations[item_id].append(ref)
            visit(item_id)

    def visit(pack_id: str) -> None:
        if pack_id in visiting:
            cycle = visiting[visiting.index(pack_id) :] + [pack_id]
            raise ResolutionError(f"Circular pack reference detected: {' -> '.join(cycle)}")
        if pack_id in visited:
            return
        resolved = resolved_items.get(pack_id)
        if resolved is None:
            raise ResolutionError(f"Missing referenced item: {pack_id}")
        if resolved.item.kind != "pack":
            raise ResolutionError(f"Pack activation referenced non-pack item as pack: {pack_id}")
        visiting.append(pack_id)
        for item_id in resolved.item.activation_required:
            activate_reference(pack_id, item_id, "required")
        for item_id in resolved.item.activation_enabled:
            activate_reference(pack_id, item_id, "enabled")
        visiting.pop()
        visited.add(pack_id)

    for pack_id in initial_pack_ids:
        visit(pack_id)
    return expanded


def merge_recommended_agent_types(layers: list[LayerData], unknown_only: bool) -> list[str]:
    values: list[str] = []
    for layer in layers:
        source = layer.config.recommended_agent_types
        if unknown_only and layer.config.layer_name not in {"org", "user"}:
            continue
        for agent_type in source:
            if agent_type not in values:
                values.append(agent_type)
    return values


def merge_recommended_item_ids(layers: list[LayerData]) -> list[str]:
    fields = [
        "recommended_skills",
        "recommended_policies",
        "recommended_contexts",
        "recommended_completion_gates",
        "recommended_packs",
        "recommended_playbooks",
        "recommended_profiles",
    ]
    values: list[str] = []
    for layer in layers:
        for field in fields:
            for item_id in getattr(layer.config, field):
                if item_id not in values:
                    values.append(item_id)
    return values


def activation_map_for_unknown(
    org_values: list[str],
    user_values: list[str],
    user_disabled: list[str],
    org_config: LayerConfig,
    user_config: LayerConfig,
) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for item_id in org_values:
        refs.setdefault(item_id, []).append(layer_ref(org_config))
    for item_id in user_values:
        refs.setdefault(item_id, [])
        user_ref = layer_ref(user_config)
        if user_ref not in refs[item_id]:
            refs[item_id].append(user_ref)
    for item_id in list(refs):
        if item_id in user_disabled:
            refs.pop(item_id, None)
    return refs


def layer_ref(config: LayerConfig) -> str:
    return f"{config.layer_name}:{config.identifier}"


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


def apply_enabled_override(resolved: ResolvedItem, layers: list[LayerData]) -> None:
    for layer in layers:
        for override in layer.config.item_overrides:
            if override.item_id == resolved.item.item_id and override.enabled is False:
                resolved.active = False


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
