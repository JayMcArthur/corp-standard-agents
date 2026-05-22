from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TargetSettings:
    mode: str | None = None
    include: bool = True
    summary_budget: str | None = None
    globs: list[str] = field(default_factory=list)
    always_apply: bool | None = None


@dataclass(slots=True)
class MachineConfig:
    corp_repo_path: Path
    user_layer_path: Path
    cache_root: Path
    default_tool_target: str = "all"
    user_name: str | None = None
    materialization_strategy: str = "auto"


@dataclass(slots=True)
class ItemOverride:
    item_id: str
    enabled: bool | None = None
    timeout_seconds: int | None = None
    recommended_agent_types: list[str] | None = None
    tags: list[str] | None = None
    source_note: str | None = None


@dataclass(slots=True)
class WorkspaceBinding:
    name: str
    path: Path
    repo_id: str | None = None
    repo_group_id: str | None = None
    profile: str | None = None
    disabled_skills: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LayerConfig:
    layer_name: str
    layer_path: Path
    identifier: str
    owner: str | None = None
    maintainer: str | None = None
    lifecycle_status: str = "active"
    review_status: str = "unreviewed"
    deprecated_by: str | None = None
    sunset_after: str | None = None
    stop_conditions: list[str] = field(default_factory=list)
    intended_consumers: list[str] = field(default_factory=list)
    context_quality_max_active_items: int | None = None
    enabled_sources: list[str] = field(default_factory=list)
    disabled_sources: list[str] = field(default_factory=list)
    enabled_skills: list[str] = field(default_factory=list)
    disabled_skills: list[str] = field(default_factory=list)
    recommended_skills: list[str] = field(default_factory=list)
    baseline_policies: list[str] = field(default_factory=list)
    optional_policies: list[str] = field(default_factory=list)
    disabled_optional_policies: list[str] = field(default_factory=list)
    recommended_policies: list[str] = field(default_factory=list)
    contexts: list[str] = field(default_factory=list)
    disabled_contexts: list[str] = field(default_factory=list)
    recommended_contexts: list[str] = field(default_factory=list)
    required_completion_gates: list[str] = field(default_factory=list)
    optional_completion_gates: list[str] = field(default_factory=list)
    disabled_optional_completion_gates: list[str] = field(default_factory=list)
    recommended_completion_gates: list[str] = field(default_factory=list)
    required_packs: list[str] = field(default_factory=list)
    enabled_packs: list[str] = field(default_factory=list)
    disabled_packs: list[str] = field(default_factory=list)
    recommended_packs: list[str] = field(default_factory=list)
    enabled_playbooks: list[str] = field(default_factory=list)
    disabled_playbooks: list[str] = field(default_factory=list)
    recommended_playbooks: list[str] = field(default_factory=list)
    enabled_profiles: list[str] = field(default_factory=list)
    disabled_profiles: list[str] = field(default_factory=list)
    recommended_profiles: list[str] = field(default_factory=list)
    recommended_agent_types: list[str] = field(default_factory=list)
    allowed_profiles: list[str] = field(default_factory=list)
    default_profile: str | None = None
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    framework_versions: dict[str, str] = field(default_factory=dict)
    repo_tags: list[str] = field(default_factory=list)
    item_overrides: list[ItemOverride] = field(default_factory=list)
    normalized_remotes: list[str] = field(default_factory=list)
    repo_group_id: str | None = None
    repo_class: str | None = None
    minimal_enabled_skills: list[str] = field(default_factory=list)
    minimal_optional_policies: list[str] = field(default_factory=list)
    minimal_contexts: list[str] = field(default_factory=list)
    protected_fields: set[str] = field(default_factory=set)
    workspace_bindings: list[WorkspaceBinding] = field(default_factory=list)


@dataclass(slots=True)
class SourceDefinition:
    source_id: str
    url: str
    commit: str
    namespace: str
    trust_mode: str
    path: Path
    source_type: str = "external"
    fingerprint: str | None = None
    trust_level: str | None = None


@dataclass(slots=True)
class SourceRef:
    source_id: str
    source_type: str
    namespace: str
    commit: str
    checkout_path: Path
    url: str
    fingerprint: str
    fingerprint_mode: str
    trust_status: str


@dataclass(slots=True)
class Item:
    item_id: str
    kind: str
    title: str
    privacy: str
    source_type: str
    source_namespace: str
    source_ref: str
    body: str
    slug: str
    item_path: Path
    body_path: Path
    owner: str | None = None
    maintainer: str | None = None
    lifecycle_status: str = "active"
    review_status: str = "unreviewed"
    deprecated_by: str | None = None
    sunset_after: str | None = None
    stop_conditions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    recommended_agent_types: list[str] = field(default_factory=list)
    timeout_seconds: int | None = None
    source_note: str | None = None
    target_tools: list[str] = field(default_factory=list)
    claude_model: str | None = None
    cursor_globs: list[str] = field(default_factory=list)
    cursor_always_apply: bool | None = None
    target_settings: dict[str, TargetSettings] = field(default_factory=dict)
    policy_rules: list[dict[str, Any]] = field(default_factory=list)
    usage_mode: str = "reusable"
    activation_required: list[str] = field(default_factory=list)
    activation_enabled: list[str] = field(default_factory=list)
    promotion_checklist: dict[str, str] = field(default_factory=dict)
    trust_level: str = "unreviewed"
    trust_level_explicit: bool = False
    allows_scripts: bool = False
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    applies_to_languages: list[str] = field(default_factory=list)
    applies_to_frameworks: list[str] = field(default_factory=list)
    compatible_versions: dict[str, str] = field(default_factory=dict)
    repo_tags: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LayerData:
    config: LayerConfig
    items: dict[str, Item]
    profiles: dict[str, LayerConfig] = field(default_factory=dict)


@dataclass(slots=True)
class CorpRepo:
    root: Path
    org: LayerData
    repo_groups: dict[str, LayerData]
    repos: dict[str, LayerData]
    sources: dict[str, SourceDefinition]


@dataclass(slots=True)
class UserLayer:
    root: Path
    layer: LayerData
    personal_sources: dict[str, SourceDefinition]
    workspace_bindings: list[WorkspaceBinding]


@dataclass(slots=True)
class WorkspaceContext:
    workspace: Path
    git_root: Path | None
    normalized_remotes: list[str]
    matched_repo_id: str | None = None
    matched_repo_group_id: str | None = None
    repo_class: str | None = None
    is_unknown: bool = False
    is_non_git: bool = False
    binding_name: str | None = None
    profile: str | None = None
    binding_disabled_skills: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResolvedItem:
    item: Item
    layer_name: str
    status: str
    activated_by: list[str] = field(default_factory=list)
    activation_reason: str | None = None
    overridden_by: list[str] = field(default_factory=list)
    replaced_from: dict[str, str] | None = None
    denied_reason: str | None = None
    active: bool = True

    def as_metadata(self, include_body: bool) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.item.item_id,
            "kind": self.item.kind,
            "title": self.item.title,
            "privacy": self.item.privacy,
            "source_type": self.item.source_type,
            "source_namespace": self.item.source_namespace,
            "source_ref": self.item.source_ref,
            "source_path": str(self.item.item_path),
            "slug": self.item.slug,
            "status": self.status,
            "lifecycle_status": self.item.lifecycle_status,
            "layer_name": self.layer_name,
            "activated_by": self.activated_by,
            "activation_reason": self.activation_reason,
            "activation_state": self.activation_reason or "active",
            "required": self.activation_reason == "required",
            "selected_by_packs": selected_by_kind(self.activated_by, "pack"),
            "selected_by_profiles": selected_by_kind(self.activated_by, "profile"),
            "target_outputs": target_outputs_for_item(self.item),
            "privacy_status": self.item.privacy,
            "trust_level": self.item.trust_level,
            "allows_scripts": self.item.allows_scripts,
            "overridden_by": self.overridden_by,
            "active": self.active,
        }
        if self.item.owner:
            data["owner"] = self.item.owner
        if self.item.maintainer:
            data["maintainer"] = self.item.maintainer
        data["review_status"] = self.item.review_status
        if self.item.deprecated_by:
            data["deprecated_by"] = self.item.deprecated_by
        if self.item.sunset_after:
            data["sunset_after"] = self.item.sunset_after
        if self.item.stop_conditions:
            data["stop_conditions"] = self.item.stop_conditions
        if self.replaced_from:
            data["replaced_from"] = self.replaced_from
        if self.denied_reason:
            data["denied_reason"] = self.denied_reason
        if self.item.tags:
            data["tags"] = self.item.tags
        if self.item.recommended_agent_types:
            data["recommended_agent_types"] = self.item.recommended_agent_types
        if self.item.timeout_seconds is not None:
            data["timeout_seconds"] = self.item.timeout_seconds
        if self.item.source_note:
            data["source_note"] = self.item.source_note
        if self.item.target_tools:
            data["target_tools"] = self.item.target_tools
        if self.item.claude_model:
            data["claude_model"] = self.item.claude_model
        if self.item.cursor_globs:
            data["cursor_globs"] = self.item.cursor_globs
        if self.item.cursor_always_apply is not None:
            data["cursor_always_apply"] = self.item.cursor_always_apply
        if self.item.target_settings:
            data["target_settings"] = {
                target: {
                    key: value
                    for key, value in {
                        "mode": settings.mode,
                        "include": settings.include,
                        "summary_budget": settings.summary_budget,
                        "globs": settings.globs,
                        "always_apply": settings.always_apply,
                    }.items()
                    if value not in (None, [])
                }
                for target, settings in sorted(self.item.target_settings.items())
            }
        if self.item.policy_rules:
            data["policy_rules"] = self.item.policy_rules
        if self.item.usage_mode != "reusable":
            data["usage_mode"] = self.item.usage_mode
        if self.item.promotion_checklist:
            data["promotion_checklist"] = self.item.promotion_checklist
        if self.item.reviewed_by:
            data["reviewed_by"] = self.item.reviewed_by
        if self.item.reviewed_at:
            data["reviewed_at"] = self.item.reviewed_at
        if self.item.applies_to_languages:
            data["applies_to_languages"] = self.item.applies_to_languages
        if self.item.applies_to_frameworks:
            data["applies_to_frameworks"] = self.item.applies_to_frameworks
        if self.item.compatible_versions:
            data["compatible_versions"] = self.item.compatible_versions
        if self.item.repo_tags:
            data["repo_tags"] = self.item.repo_tags
        if self.item.inputs:
            data["inputs"] = self.item.inputs
        if self.item.outputs:
            data["outputs"] = self.item.outputs
        if self.item.evidence_required:
            data["evidence_required"] = self.item.evidence_required
        if self.item.activation_required or self.item.activation_enabled:
            data["activation"] = {
                key: value
                for key, value in {
                    "required": self.item.activation_required,
                    "enabled": self.item.activation_enabled,
                }.items()
                if value
            }
        if include_body:
            data["body"] = self.item.body
        return data


def selected_by_kind(activated_by: list[str], prefix: str) -> list[str]:
    marker = f"{prefix}:"
    return [value.removeprefix(marker) for value in activated_by if value.startswith(marker)]


def target_outputs_for_item(item: Item) -> list[str]:
    outputs: list[str] = []
    for target in ["claude", "codex", "cursor"]:
        settings = item.target_settings.get(target)
        if settings is not None:
            if settings.include:
                outputs.append(target)
            continue
        if not item.target_tools or target in item.target_tools:
            outputs.append(target)
    return outputs


@dataclass(slots=True)
class ResolutionResult:
    workspace_context: WorkspaceContext
    layer_chain: list[str]
    applied_layers: list[dict[str, str]]
    enabled_sources: list[str]
    source_details: dict[str, SourceRef]
    enabled_skills: list[str]
    active_policies: list[str]
    active_contexts: list[str]
    active_completion_gates: list[str]
    active_packs: list[str]
    active_playbooks: list[str]
    active_profiles: list[str]
    recommended_items: list[str]
    recommended_agent_types: list[str]
    items: dict[str, ResolvedItem]
    warnings: list[str] = field(default_factory=list)
    denied_items: dict[str, ResolvedItem] = field(default_factory=dict)
    selected_profile_configs: list[LayerConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        repo_class = self.workspace_context.repo_class or "unknown"
        result: dict[str, Any] = {
            "schema_version": "v1",
            "workspace": str(self.workspace_context.workspace),
            "git_root": str(self.workspace_context.git_root) if self.workspace_context.git_root else None,
            "normalized_remotes": self.workspace_context.normalized_remotes,
            "matched_repo_id": self.workspace_context.matched_repo_id,
            "matched_repo_group_id": self.workspace_context.matched_repo_group_id,
            "binding_name": self.workspace_context.binding_name,
            "profile": self.workspace_context.profile,
            "repo_class": repo_class,
            "layer_chain": self.layer_chain,
            "applied_layers": self.applied_layers,
            "enabled_sources": self.enabled_sources,
            "source_details": {
                source_id: {
                    "source_type": source_ref.source_type,
                    "namespace": source_ref.namespace,
                    "commit": source_ref.commit,
                    "url": source_ref.url,
                    "checkout_path": str(source_ref.checkout_path),
                    "fingerprint": source_ref.fingerprint,
                    "fingerprint_mode": source_ref.fingerprint_mode,
                    "trust_status": source_ref.trust_status,
                }
                for source_id, source_ref in sorted(self.source_details.items())
            },
            "enabled_skills": self.enabled_skills,
            "active_policies": self.active_policies,
            "active_contexts": self.active_contexts,
            "active_completion_gates": self.active_completion_gates,
            "active_packs": self.active_packs,
            "active_playbooks": self.active_playbooks,
            "active_profiles": self.active_profiles,
            "recommended_items": self.recommended_items,
            "recommended_agent_types": self.recommended_agent_types,
            "warnings": self.warnings,
            "selected_profile_configs": [
                {
                    key: value
                    for key, value in {
                        "id": profile.identifier,
                        "layer_name": profile.layer_name,
                        "owner": profile.owner,
                        "maintainer": profile.maintainer,
                        "status": profile.lifecycle_status,
                        "review_status": profile.review_status,
                        "stop_conditions": profile.stop_conditions,
                        "intended_consumers": profile.intended_consumers,
                    }.items()
                    if value not in (None, [])
                }
                for profile in self.selected_profile_configs
            ],
            "items": {},
            "denied_items": {},
        }
        for item_id, resolved in sorted(self.items.items()):
            include_body = not (repo_class == "client" and resolved.item.privacy == "corp-private")
            result["items"][item_id] = resolved.as_metadata(include_body=include_body)
        for item_id, resolved in sorted(self.denied_items.items()):
            result["denied_items"][item_id] = resolved.as_metadata(include_body=False)
        return result
