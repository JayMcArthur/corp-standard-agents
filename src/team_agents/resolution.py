from __future__ import annotations

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
    UserOverrides,
    WorkspaceBinding,
    WorkspaceContext,
)
from team_agents.sources import load_source_items, materialize_source


def build_workspace_context(workspace: Path, corp: CorpRepo, user: UserOverrides) -> WorkspaceContext:
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
        return WorkspaceContext(
            workspace=workspace,
            git_root=git_root,
            normalized_remotes=remotes,
            is_unknown=True,
        )
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
    user: UserOverrides,
) -> ResolutionResult:
    context = build_workspace_context(workspace, corp, user)
    layers = select_layers(context, corp, user)
    enabled_sources = merge_sources(layers)
    resolved_items, source_details = gather_items(layers, enabled_sources, machine_config, corp, user)
    enabled_skills = merge_set_fields(layers, "enabled_skills", "disabled_skills")
    optional_policies = merge_set_fields(layers, "optional_policies", "disabled_optional_policies")
    docs = merge_set_fields(layers, "docs", "disabled_docs")
    baseline_policies = list(dict.fromkeys(corp.org.config.baseline_policies))
    if context.is_unknown:
        user_layer = user.layer.config
        enabled_skills = (set(corp.org.config.minimal_enabled_skills) | set(user_layer.enabled_skills)) - set(user_layer.disabled_skills)
        optional_policies = (set(corp.org.config.minimal_optional_policies) | set(user_layer.optional_policies)) - set(
            user_layer.disabled_optional_policies
        )
        docs = (set(corp.org.config.minimal_docs) | set(user_layer.docs)) - set(user_layer.disabled_docs)
    active_policy_ids = baseline_policies + [item_id for item_id in optional_policies if item_id not in baseline_policies]
    recommended_agent_types = merge_recommended_agent_types(layers, unknown_only=context.is_unknown)
    active_ids = set(enabled_skills) | set(active_policy_ids) | set(docs)
    active_items: dict[str, ResolvedItem] = {}
    denied_items: dict[str, ResolvedItem] = {}
    warnings: list[str] = []
    for item_id in active_ids:
        resolved = resolved_items.get(item_id)
        if resolved is None:
            raise ResolutionError(f"Missing referenced item: {item_id}")
        apply_enabled_override(resolved, layers)
        if not resolved.active:
            denied_items[item_id] = resolved
            continue
        denial = evaluate_item_eligibility(context, resolved, item_id in baseline_policies)
        if denial:
            resolved.denied_reason = denial
            denied_items[item_id] = resolved
            if resolved.item.kind in {"skill", "policy", "doc"}:
                raise ResolutionError(f"{item_id} is not allowed in this workspace: {denial}")
            continue
        active_items[item_id] = resolved
    for item_id, resolved in resolved_items.items():
        if item_id not in active_ids and resolved.denied_reason:
            denied_items[item_id] = resolved
    if any(
        override.item_id in corp.org.config.baseline_policies and override.enabled is False
        for override in user.layer.config.item_overrides
    ):
        raise ResolutionError("User overrides may not disable baseline policies")
    if any(
        field in user.layer.config.protected_fields
        for field in corp.org.config.protected_fields
    ):
        warnings.append("User protected field overlap ignored")
    return ResolutionResult(
        workspace_context=context,
        enabled_sources=enabled_sources,
        source_details=source_details,
        enabled_skills=sorted(item_id for item_id in enabled_skills if item_id in active_items),
        active_policies=sorted(item_id for item_id in active_policy_ids if item_id in active_items),
        active_docs=sorted(item_id for item_id in docs if item_id in active_items),
        recommended_agent_types=recommended_agent_types,
        items=active_items,
        denied_items=denied_items,
        warnings=warnings,
    )


def select_layers(context: WorkspaceContext, corp: CorpRepo, user: UserOverrides) -> list[LayerData]:
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


def merge_sources(layers: list[LayerData]) -> list[str]:
    enabled: list[str] = []
    disabled: set[str] = set()
    for layer in layers:
        for source_id in layer.config.enabled_sources:
            if source_id not in enabled:
                enabled.append(source_id)
        disabled.update(layer.config.disabled_sources)
    return [source_id for source_id in enabled if source_id not in disabled]


def merge_set_fields(layers: list[LayerData], enabled_field: str, disabled_field: str) -> set[str]:
    enabled: list[str] = []
    disabled: set[str] = set()
    for layer in layers:
        for item_id in getattr(layer.config, enabled_field):
            if item_id not in enabled:
                enabled.append(item_id)
        disabled.update(getattr(layer.config, disabled_field))
    return {item_id for item_id in enabled if item_id not in disabled}


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


def gather_items(
    layers: list[LayerData],
    enabled_sources: list[str],
    machine_config: MachineConfig,
    corp: CorpRepo,
    user: UserOverrides,
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
        return "baseline policies are protected"
    return None


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
