from __future__ import annotations

from pathlib import Path
from typing import Any

from team_agents.errors import ValidationError
from team_agents.loading_parsing import (
    config_list,
    optional_int,
    optional_str,
    parse_lifecycle_status,
    parse_review_status,
    str_dict,
    str_list,
)
from team_agents.models import ItemOverride, LayerConfig, WorkspaceBinding
from team_agents.toml_utils import read_toml
from team_agents.validation import validate_canonical_id, validate_repo_class

OVERRIDE_KEYS = {"enabled", "timeout_seconds", "recommended_agent_types", "tags", "source_note"}


def load_layer_config(path: Path, layer_name: str) -> LayerConfig:
    config_path = path / "config.toml"
    raw = read_toml(config_path)
    identifier = str(raw.get("id") or raw.get("repo_id") or raw.get("org_id") or path.name)
    config = LayerConfig(
        layer_name=layer_name,
        layer_path=path,
        identifier=identifier,
        owner=optional_str(raw.get("owner")),
        maintainer=optional_str(raw.get("maintainer")),
        lifecycle_status=parse_lifecycle_status(raw.get("status"), config_path),
        review_status=parse_review_status(raw.get("review_status"), config_path),
        deprecated_by=optional_str(raw.get("deprecated_by")),
        sunset_after=optional_str(raw.get("sunset_after")),
        stop_conditions=str_list(raw.get("stop_conditions")),
        intended_consumers=str_list(raw.get("intended_consumers")),
        context_quality_max_active_items=optional_int(raw.get("context_quality_max_active_items")),
        enabled_sources=str_list(raw.get("enabled_sources")),
        disabled_sources=str_list(raw.get("disabled_sources")),
        enabled_skills=config_list(raw, "skills", "enabled", "enabled_skills"),
        disabled_skills=config_list(raw, "skills", "disabled", "disabled_skills"),
        recommended_skills=config_list(raw, "skills", "recommended", "recommended_skills"),
        baseline_policies=config_list(raw, "policies", "required", "baseline_policies"),
        optional_policies=config_list(raw, "policies", "enabled", "optional_policies"),
        disabled_optional_policies=config_list(raw, "policies", "disabled", "disabled_optional_policies"),
        recommended_policies=config_list(raw, "policies", "recommended", "recommended_policies"),
        contexts=config_list(raw, "contexts", "enabled", "contexts"),
        disabled_contexts=config_list(raw, "contexts", "disabled", "disabled_contexts"),
        recommended_contexts=config_list(raw, "contexts", "recommended", "recommended_contexts"),
        required_completion_gates=config_list(raw, "completion_gates", "required", "required_completion_gates"),
        optional_completion_gates=config_list(raw, "completion_gates", "enabled", "optional_completion_gates"),
        disabled_optional_completion_gates=config_list(raw, "completion_gates", "disabled", "disabled_optional_completion_gates"),
        recommended_completion_gates=config_list(raw, "completion_gates", "recommended", "recommended_completion_gates"),
        required_packs=config_list(raw, "packs", "required", "required_packs"),
        enabled_packs=config_list(raw, "packs", "enabled", "enabled_packs"),
        disabled_packs=config_list(raw, "packs", "disabled", "disabled_packs"),
        recommended_packs=config_list(raw, "packs", "recommended", "recommended_packs"),
        enabled_playbooks=config_list(raw, "playbooks", "enabled", "enabled_playbooks"),
        disabled_playbooks=config_list(raw, "playbooks", "disabled", "disabled_playbooks"),
        recommended_playbooks=config_list(raw, "playbooks", "recommended", "recommended_playbooks"),
        enabled_profiles=config_list(raw, "profiles", "enabled", "enabled_profiles"),
        disabled_profiles=config_list(raw, "profiles", "disabled", "disabled_profiles"),
        recommended_profiles=config_list(raw, "profiles", "recommended", "recommended_profiles"),
        recommended_agent_types=str_list(raw.get("recommended_agent_types", raw.get("preferred_agent_types"))),
        allowed_profiles=str_list(raw.get("allowed_profiles")),
        default_profile=raw.get("default_profile"),
        languages=str_list(raw.get("languages")),
        frameworks=str_list(raw.get("frameworks")),
        framework_versions=str_dict(raw.get("framework_versions")),
        repo_tags=str_list(raw.get("repo_tags")),
        item_overrides=parse_item_overrides(raw.get("item_override", []), config_path),
        normalized_remotes=str_list(raw.get("normalized_remotes")),
        repo_group_id=raw.get("repo_group_id"),
        repo_class=raw.get("repo_class"),
        minimal_enabled_skills=str_list(raw.get("minimal_enabled_skills")),
        minimal_optional_policies=str_list(raw.get("minimal_optional_policies")),
        minimal_contexts=str_list(raw.get("minimal_contexts")),
        protected_fields=set(str_list(raw.get("protected_fields"))),
    )
    apply_generalized_activation(config, raw, config_path)
    validate_layer_config(config, config_path)
    return config


def load_profile_configs(layer_root: Path) -> dict[str, LayerConfig]:
    profiles_root = layer_root / "profiles"
    if not profiles_root.exists():
        return {}
    profiles: dict[str, LayerConfig] = {}
    for profile_path in sorted(profiles_root.glob("*.toml")):
        if profile_path.name == "item.toml":
            continue
        raw = read_toml(profile_path)
        identifier = str(raw.get("id") or profile_path.stem)
        config = LayerConfig(
            layer_name="profile",
            layer_path=profile_path,
            identifier=identifier,
            owner=optional_str(raw.get("owner")),
            maintainer=optional_str(raw.get("maintainer")),
            lifecycle_status=parse_lifecycle_status(raw.get("status"), profile_path),
            review_status=parse_review_status(raw.get("review_status"), profile_path),
            deprecated_by=optional_str(raw.get("deprecated_by")),
            sunset_after=optional_str(raw.get("sunset_after")),
            stop_conditions=str_list(raw.get("stop_conditions")),
            intended_consumers=str_list(raw.get("intended_consumers")),
            context_quality_max_active_items=optional_int(raw.get("context_quality_max_active_items")),
            enabled_skills=config_list(raw, "skills", "enabled", "enabled_skills"),
            disabled_skills=config_list(raw, "skills", "disabled", "disabled_skills"),
            recommended_skills=config_list(raw, "skills", "recommended", "recommended_skills"),
            baseline_policies=config_list(raw, "policies", "required", "baseline_policies"),
            optional_policies=config_list(raw, "policies", "enabled", "optional_policies"),
            disabled_optional_policies=config_list(raw, "policies", "disabled", "disabled_optional_policies"),
            recommended_policies=config_list(raw, "policies", "recommended", "recommended_policies"),
            contexts=config_list(raw, "contexts", "enabled", "contexts"),
            disabled_contexts=config_list(raw, "contexts", "disabled", "disabled_contexts"),
            recommended_contexts=config_list(raw, "contexts", "recommended", "recommended_contexts"),
            required_completion_gates=config_list(raw, "completion_gates", "required", "required_completion_gates"),
            optional_completion_gates=config_list(raw, "completion_gates", "enabled", "optional_completion_gates"),
            disabled_optional_completion_gates=config_list(raw, "completion_gates", "disabled", "disabled_optional_completion_gates"),
            recommended_completion_gates=config_list(raw, "completion_gates", "recommended", "recommended_completion_gates"),
            required_packs=config_list(raw, "packs", "required", "required_packs"),
            enabled_packs=config_list(raw, "packs", "enabled", "enabled_packs"),
            disabled_packs=config_list(raw, "packs", "disabled", "disabled_packs"),
            recommended_packs=config_list(raw, "packs", "recommended", "recommended_packs"),
            enabled_playbooks=config_list(raw, "playbooks", "enabled", "enabled_playbooks"),
            disabled_playbooks=config_list(raw, "playbooks", "disabled", "disabled_playbooks"),
            recommended_playbooks=config_list(raw, "playbooks", "recommended", "recommended_playbooks"),
            enabled_profiles=config_list(raw, "profiles", "enabled", "enabled_profiles"),
            disabled_profiles=config_list(raw, "profiles", "disabled", "disabled_profiles"),
            recommended_profiles=config_list(raw, "profiles", "recommended", "recommended_profiles"),
            recommended_agent_types=str_list(raw.get("recommended_agent_types", raw.get("preferred_agent_types"))),
            languages=str_list(raw.get("languages")),
            frameworks=str_list(raw.get("frameworks")),
            framework_versions=str_dict(raw.get("framework_versions")),
            repo_tags=str_list(raw.get("repo_tags")),
        )
        apply_generalized_activation(config, raw, profile_path)
        profiles[identifier] = config
    return profiles


def apply_generalized_activation(config: LayerConfig, raw: dict[str, Any], config_path: Path) -> None:
    activation = raw.get("activation")
    if activation is None:
        return
    if not isinstance(activation, dict):
        raise ValidationError(f"[activation] must be a table in {config_path}")
    unknown = set(activation) - {"required", "enabled", "disabled", "recommended"}
    if unknown:
        raise ValidationError(f"Unsupported activation fields in {config_path}: {', '.join(sorted(unknown))}")
    for item_id in str_list(activation.get("required")):
        add_activation_id(config, item_id, "required", config_path)
    for item_id in str_list(activation.get("enabled")):
        add_activation_id(config, item_id, "enabled", config_path)
    for item_id in str_list(activation.get("disabled")):
        add_activation_id(config, item_id, "disabled", config_path)
    for item_id in str_list(activation.get("recommended")):
        add_activation_id(config, item_id, "recommended", config_path)


def add_activation_id(config: LayerConfig, item_id: str, mode: str, config_path: Path) -> None:
    _, _, kind, _ = validate_canonical_id(item_id, path=config_path)
    field_by_mode = {
        "required": {
            "policy": "baseline_policies",
            "completion_gate": "required_completion_gates",
            "pack": "required_packs",
        },
        "enabled": {
            "skill": "enabled_skills",
            "policy": "optional_policies",
            "context": "contexts",
            "completion_gate": "optional_completion_gates",
            "pack": "enabled_packs",
            "playbook": "enabled_playbooks",
            "profile": "enabled_profiles",
        },
        "disabled": {
            "skill": "disabled_skills",
            "policy": "disabled_optional_policies",
            "context": "disabled_contexts",
            "completion_gate": "disabled_optional_completion_gates",
            "pack": "disabled_packs",
            "playbook": "disabled_playbooks",
            "profile": "disabled_profiles",
        },
        "recommended": {
            "skill": "recommended_skills",
            "policy": "recommended_policies",
            "context": "recommended_contexts",
            "completion_gate": "recommended_completion_gates",
            "pack": "recommended_packs",
            "playbook": "recommended_playbooks",
            "profile": "recommended_profiles",
        },
    }
    field = field_by_mode[mode].get(kind)
    if field is None:
        raise ValidationError(f"activation.{mode} does not support {kind} items in {config_path}: {item_id}")
    values = getattr(config, field)
    if item_id not in values:
        values.append(item_id)


def parse_item_overrides(entries: Any, config_path: Path) -> list[ItemOverride]:
    if not entries:
        return []
    result: list[ItemOverride] = []
    for entry in entries:
        item_id = entry.get("id")
        if not item_id:
            raise ValidationError(f"Item override missing id in {config_path}")
        validate_canonical_id(str(item_id), path=config_path)
        unknown = set(entry) - (OVERRIDE_KEYS | {"id"})
        if unknown:
            raise ValidationError(f"Unsupported item override fields in {config_path}: {', '.join(sorted(unknown))}")
        result.append(
            ItemOverride(
                item_id=str(item_id),
                enabled=entry.get("enabled"),
                timeout_seconds=optional_int(entry.get("timeout_seconds")),
                recommended_agent_types=str_list(entry.get("recommended_agent_types")),
                tags=str_list(entry.get("tags")),
                source_note=entry.get("source_note"),
            )
        )
    return result


def parse_workspace_bindings(entries: Any, root: Path) -> list[WorkspaceBinding]:
    if not entries:
        return []
    bindings: list[WorkspaceBinding] = []
    for entry in entries:
        if "name" not in entry or "path" not in entry:
            raise ValidationError(f"Workspace binding missing name/path in {root / 'config.toml'}")
        if entry.get("repo_id") and entry.get("repo_group_id"):
            raise ValidationError(f"Workspace binding may set repo_id or repo_group_id, not both, in {root / 'config.toml'}")
        bindings.append(
            WorkspaceBinding(
                name=str(entry["name"]),
                path=Path(str(entry["path"])).expanduser().resolve(),
                repo_id=entry.get("repo_id"),
                repo_group_id=entry.get("repo_group_id"),
                profile=entry.get("profile"),
                disabled_skills=str_list(entry.get("disabled_skills")),
            )
        )
    return bindings


def validate_layer_config(config: LayerConfig, config_path: Path) -> None:
    if config.layer_name == "org":
        if config.repo_group_id or config.repo_class or config.normalized_remotes:
            raise ValidationError(f"Org config may not declare repo binding fields in {config_path}")
    elif config.layer_name == "repo-group":
        if config.repo_group_id or config.repo_class or config.normalized_remotes:
            raise ValidationError(f"Repo-group config may not declare repo binding fields in {config_path}")
    elif config.layer_name == "repo":
        validate_repo_class(config.repo_class, config_path)
        if not config.normalized_remotes:
            raise ValidationError(f"Repo config must declare normalized_remotes in {config_path}")
    elif config.layer_name == "user":
        if config.baseline_policies:
            raise ValidationError(f"User layer config may not declare baseline_policies in {config_path}")
        if config.repo_group_id or config.repo_class or config.normalized_remotes:
            raise ValidationError(f"User layer config may not declare repo binding fields in {config_path}")
