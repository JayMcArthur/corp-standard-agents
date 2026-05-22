from __future__ import annotations

from dataclasses import dataclass, field

from team_agents.errors import ResolutionError
from team_agents.models import LayerConfig, LayerData, ResolvedItem
from team_agents.validation import validate_canonical_id


@dataclass(slots=True)
class ActivationSelection:
    enabled_skills: set[str] = field(default_factory=set)
    active_policy_ids: list[str] = field(default_factory=list)
    active_context_ids: set[str] = field(default_factory=set)
    active_completion_gate_ids: list[str] = field(default_factory=list)
    active_pack_ids: list[str] = field(default_factory=list)
    active_playbook_ids: set[str] = field(default_factory=set)
    active_profile_ids: set[str] = field(default_factory=set)
    recommended_item_ids: list[str] = field(default_factory=list)
    recommended_agent_types: list[str] = field(default_factory=list)
    activation_map: dict[str, list[str]] = field(default_factory=dict)
    activation_reasons: dict[str, str] = field(default_factory=dict)
    required_item_ids: set[str] = field(default_factory=set)

    @property
    def active_ids(self) -> set[str]:
        return (
            set(self.enabled_skills)
            | set(self.active_policy_ids)
            | set(self.active_context_ids)
            | set(self.active_completion_gate_ids)
            | set(self.active_pack_ids)
            | set(self.active_playbook_ids)
            | set(self.active_profile_ids)
        )


def select_activations(
    *,
    activation_layers: list[LayerData],
    resolved_items: dict[str, ResolvedItem],
    org_config: LayerConfig,
    user_config: LayerConfig,
    is_unknown_workspace: bool,
    binding_disabled_skills: list[str] | None = None,
) -> ActivationSelection:
    enabled_skills, skill_activations = merge_set_fields(activation_layers, "enabled_skills", "disabled_skills")
    optional_policies, policy_activations = merge_set_fields(
        activation_layers, "optional_policies", "disabled_optional_policies"
    )
    contexts, context_activations = merge_set_fields(activation_layers, "contexts", "disabled_contexts")
    optional_completion_gates, completion_gate_activations = merge_set_fields(
        activation_layers, "optional_completion_gates", "disabled_optional_completion_gates"
    )
    enabled_packs, pack_activations = merge_set_fields(activation_layers, "enabled_packs", "disabled_packs")
    enabled_playbooks, playbook_activations = merge_set_fields(activation_layers, "enabled_playbooks", "disabled_playbooks")
    enabled_profiles, profile_activations = merge_set_fields(activation_layers, "enabled_profiles", "disabled_profiles")
    baseline_policies = list(dict.fromkeys(org_config.baseline_policies))
    baseline_policy_activations = {item_id: [layer_ref(org_config)] for item_id in baseline_policies}
    required_completion_gates = merge_required_field(activation_layers, "required_completion_gates")
    required_completion_gate_activations = activation_map_for_required(activation_layers, "required_completion_gates")
    required_packs = merge_required_field(activation_layers, "required_packs")
    required_pack_activations = activation_map_for_required(activation_layers, "required_packs")

    if is_unknown_workspace:
        enabled_skills = (set(org_config.minimal_enabled_skills) | set(user_config.enabled_skills)) - set(
            user_config.disabled_skills
        )
        optional_policies = (set(org_config.minimal_optional_policies) | set(user_config.optional_policies)) - set(
            user_config.disabled_optional_policies
        )
        contexts = (set(org_config.minimal_contexts) | set(user_config.contexts)) - set(user_config.disabled_contexts)
        optional_completion_gates = set(user_config.optional_completion_gates) - set(user_config.disabled_optional_completion_gates)
        enabled_packs = set(user_config.enabled_packs) - set(user_config.disabled_packs)
        enabled_playbooks = set(user_config.enabled_playbooks) - set(user_config.disabled_playbooks)
        enabled_profiles = set(user_config.enabled_profiles) - set(user_config.disabled_profiles)
        skill_activations = activation_map_for_unknown(
            org_config.minimal_enabled_skills,
            user_config.enabled_skills,
            user_config.disabled_skills,
            org_config,
            user_config,
        )
        policy_activations = activation_map_for_unknown(
            org_config.minimal_optional_policies,
            user_config.optional_policies,
            user_config.disabled_optional_policies,
            org_config,
            user_config,
        )
        context_activations = activation_map_for_unknown(
            org_config.minimal_contexts,
            user_config.contexts,
            user_config.disabled_contexts,
            org_config,
            user_config,
        )
        completion_gate_activations = activation_map_for_unknown(
            [],
            user_config.optional_completion_gates,
            user_config.disabled_optional_completion_gates,
            org_config,
            user_config,
        )
        pack_activations = activation_map_for_unknown(
            [],
            user_config.enabled_packs,
            user_config.disabled_packs,
            org_config,
            user_config,
        )
        playbook_activations = activation_map_for_unknown(
            [],
            user_config.enabled_playbooks,
            user_config.disabled_playbooks,
            org_config,
            user_config,
        )
        profile_activations = activation_map_for_unknown(
            [],
            user_config.enabled_profiles,
            user_config.disabled_profiles,
            org_config,
            user_config,
        )

    if binding_disabled_skills:
        disabled = set(binding_disabled_skills)
        enabled_skills = set(enabled_skills) - disabled
        for item_id in list(skill_activations):
            if item_id in disabled:
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
        enabled_skills.update(pack_expansion.enabled_skills)
        optional_policies.update(pack_expansion.optional_policies)
        contexts.update(pack_expansion.contexts)
        optional_completion_gates.update(pack_expansion.optional_completion_gates)
        enabled_packs.update(pack_expansion.enabled_packs)
        enabled_playbooks.update(pack_expansion.enabled_playbooks)
        for item_id in pack_expansion.baseline_policies:
            if item_id not in active_policy_ids:
                active_policy_ids.append(item_id)
        for item_id in pack_expansion.required_completion_gates:
            if item_id not in active_completion_gate_ids:
                active_completion_gate_ids.append(item_id)
        for item_id in pack_expansion.required_packs:
            if item_id not in active_pack_ids:
                active_pack_ids.append(item_id)
        for item_id in pack_expansion.active_packs:
            if item_id not in active_pack_ids:
                active_pack_ids.append(item_id)
        pack_expansion_activations = pack_expansion.activations
        pack_required_items = set(pack_expansion.required_items)
    for item_id in optional_policies:
        if item_id not in active_policy_ids:
            active_policy_ids.append(item_id)
    for item_id in optional_completion_gates:
        if item_id not in active_completion_gate_ids:
            active_completion_gate_ids.append(item_id)
    for item_id in enabled_packs:
        if item_id not in active_pack_ids:
            active_pack_ids.append(item_id)

    required_item_ids = set(baseline_policies) | set(required_completion_gates) | set(required_packs) | pack_required_items
    activation_reasons = {item_id: "required" for item_id in required_item_ids}
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

    return ActivationSelection(
        enabled_skills=enabled_skills,
        active_policy_ids=active_policy_ids,
        active_context_ids=contexts,
        active_completion_gate_ids=active_completion_gate_ids,
        active_pack_ids=active_pack_ids,
        active_playbook_ids=enabled_playbooks,
        active_profile_ids=enabled_profiles,
        recommended_item_ids=merge_recommended_item_ids(activation_layers),
        recommended_agent_types=merge_recommended_agent_types(activation_layers, unknown_only=is_unknown_workspace),
        activation_map=merge_activation_maps(
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
        ),
        activation_reasons=activation_reasons,
        required_item_ids=required_item_ids,
    )


@dataclass(slots=True)
class PackExpansion:
    enabled_skills: set[str] = field(default_factory=set)
    baseline_policies: set[str] = field(default_factory=set)
    optional_policies: set[str] = field(default_factory=set)
    contexts: set[str] = field(default_factory=set)
    required_completion_gates: set[str] = field(default_factory=set)
    optional_completion_gates: set[str] = field(default_factory=set)
    required_packs: set[str] = field(default_factory=set)
    enabled_packs: set[str] = field(default_factory=set)
    enabled_playbooks: set[str] = field(default_factory=set)
    active_packs: set[str] = field(default_factory=set)
    required_items: set[str] = field(default_factory=set)
    activations: dict[str, list[str]] = field(default_factory=dict)


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
) -> PackExpansion:
    expanded = PackExpansion(active_packs=set(initial_pack_ids))
    visiting: list[str] = []
    visited: set[str] = set()

    def add_activation(item_id: str, refs: list[str]) -> None:
        expanded.activations.setdefault(item_id, [])
        for ref in refs:
            if ref not in expanded.activations[item_id]:
                expanded.activations[item_id].append(ref)

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
        target = getattr(expanded, field_by_kind[kind])
        target.add(item_id)
        if mode == "required":
            expanded.required_items.add(item_id)
        refs = refs_for_pack(pack_id)
        add_activation(item_id, refs)
        if kind == "pack":
            expanded.active_packs.add(item_id)
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


def apply_enabled_override(resolved: ResolvedItem, layers: list[LayerData]) -> None:
    for layer in layers:
        for override in layer.config.item_overrides:
            if override.item_id == resolved.item.item_id and override.enabled is False:
                resolved.active = False
