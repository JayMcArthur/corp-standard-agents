from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class MachineConfig:
    corp_repo_path: Path
    user_override_path: Path
    cache_root: Path
    default_tool_target: str = "codex"


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


@dataclass(slots=True)
class LayerConfig:
    layer_name: str
    layer_path: Path
    identifier: str
    enabled_sources: list[str] = field(default_factory=list)
    disabled_sources: list[str] = field(default_factory=list)
    enabled_skills: list[str] = field(default_factory=list)
    disabled_skills: list[str] = field(default_factory=list)
    baseline_policies: list[str] = field(default_factory=list)
    optional_policies: list[str] = field(default_factory=list)
    disabled_optional_policies: list[str] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)
    disabled_docs: list[str] = field(default_factory=list)
    recommended_agent_types: list[str] = field(default_factory=list)
    item_overrides: list[ItemOverride] = field(default_factory=list)
    normalized_remotes: list[str] = field(default_factory=list)
    repo_group_id: str | None = None
    repo_class: str | None = None
    minimal_enabled_skills: list[str] = field(default_factory=list)
    minimal_optional_policies: list[str] = field(default_factory=list)
    minimal_docs: list[str] = field(default_factory=list)
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
    tags: list[str] = field(default_factory=list)
    recommended_agent_types: list[str] = field(default_factory=list)
    timeout_seconds: int | None = None
    source_note: str | None = None


@dataclass(slots=True)
class LayerData:
    config: LayerConfig
    items: dict[str, Item]


@dataclass(slots=True)
class CorpRepo:
    root: Path
    org: LayerData
    repo_groups: dict[str, LayerData]
    repos: dict[str, LayerData]
    sources: dict[str, SourceDefinition]


@dataclass(slots=True)
class UserOverrides:
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


@dataclass(slots=True)
class ResolvedItem:
    item: Item
    layer_name: str
    status: str
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
            "slug": self.item.slug,
            "status": self.status,
            "layer_name": self.layer_name,
            "overridden_by": self.overridden_by,
            "active": self.active,
        }
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
        if include_body:
            data["body"] = self.item.body
        return data


@dataclass(slots=True)
class ResolutionResult:
    workspace_context: WorkspaceContext
    enabled_sources: list[str]
    source_details: dict[str, SourceRef]
    enabled_skills: list[str]
    active_policies: list[str]
    active_docs: list[str]
    recommended_agent_types: list[str]
    items: dict[str, ResolvedItem]
    warnings: list[str] = field(default_factory=list)
    denied_items: dict[str, ResolvedItem] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        repo_class = self.workspace_context.repo_class or "unknown"
        result: dict[str, Any] = {
            "workspace": str(self.workspace_context.workspace),
            "git_root": str(self.workspace_context.git_root) if self.workspace_context.git_root else None,
            "normalized_remotes": self.workspace_context.normalized_remotes,
            "matched_repo_id": self.workspace_context.matched_repo_id,
            "matched_repo_group_id": self.workspace_context.matched_repo_group_id,
            "binding_name": self.workspace_context.binding_name,
            "repo_class": repo_class,
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
            "active_docs": self.active_docs,
            "recommended_agent_types": self.recommended_agent_types,
            "warnings": self.warnings,
            "items": {},
            "denied_items": {},
        }
        for item_id, resolved in sorted(self.items.items()):
            include_body = not (repo_class == "client" and resolved.item.privacy == "corp-private")
            result["items"][item_id] = resolved.as_metadata(include_body=include_body)
        for item_id, resolved in sorted(self.denied_items.items()):
            result["denied_items"][item_id] = resolved.as_metadata(include_body=False)
        return result
