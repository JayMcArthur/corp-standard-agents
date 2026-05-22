from __future__ import annotations

from pathlib import Path
from typing import Any

from team_agents.errors import ValidationError
from team_agents.frontmatter import parse_frontmatter_document
from team_agents.item_schema import validate_item_toml
from team_agents.models import (
    CorpRepo,
    Item,
    ItemOverride,
    LayerConfig,
    LayerData,
    SourceDefinition,
    TargetSettings,
    UserLayer,
    WorkspaceBinding,
)
from team_agents.toml_utils import read_toml
from team_agents.validation import validate_canonical_id, validate_commit_hash, validate_repo_class, validate_source_id


VALID_KINDS = {
    "skill": "skills",
    "policy": "policies",
    "context": "contexts",
    "completion_gate": "completion_gates",
    "playbook": "playbooks",
    "pack": "packs",
    "profile": "profiles",
}
VALID_PRIVACY = {"corp-private", "repo-safe"}
VALID_SOURCE_TYPES = {"corp", "external", "user"}
VALID_TRUST_LEVELS = {"unreviewed", "user-trusted", "corp-reviewed", "corp-required"}
VALID_LIFECYCLE_STATUSES = {"draft", "active", "deprecated", "archived"}
VALID_REVIEW_STATUSES = {"unreviewed", "reviewed", "approved"}
OVERRIDE_KEYS = {"enabled", "timeout_seconds", "recommended_agent_types", "tags", "source_note"}


def load_corp_repo(root: Path) -> CorpRepo:
    root = root.resolve()
    if not root.exists():
        raise ValidationError(f"Corp repo path does not exist: {root}")
    org = load_layer(root / "org", "org", source_type="corp")
    repo_groups = load_layer_map(root / "repo-groups", "repo-group")
    repos = load_layer_map(root / "repos", "repo")
    sources = load_source_registry(root)
    validate_repo_indexes(root, repo_groups, repos, sources)
    for repo_id, layer in repos.items():
        if layer.config.repo_group_id and layer.config.repo_group_id not in repo_groups:
            raise ValidationError(
                f"Repo {repo_id} references unknown repo-group {layer.config.repo_group_id} in {layer.config.layer_path / 'config.toml'}"
            )
    return CorpRepo(root=root, org=org, repo_groups=repo_groups, repos=repos, sources=sources)


def load_user_layer(root: Path) -> UserLayer:
    root = root.resolve()
    if not root.exists():
        raise ValidationError(f"User layer path does not exist: {root}")
    layer = load_layer(root, "user", source_type="user")
    data = read_toml(root / "config.toml")
    personal_sources = load_personal_sources(root / "sources")
    workspace_bindings = parse_workspace_bindings(data.get("workspace_binding", []), root)
    layer.config.workspace_bindings = workspace_bindings
    return UserLayer(root=root, layer=layer, personal_sources=personal_sources, workspace_bindings=workspace_bindings)


def load_layer_map(parent: Path, layer_name: str) -> dict[str, LayerData]:
    if not parent.exists():
        return {}
    layers: dict[str, LayerData] = {}
    for child in sorted(path for path in parent.iterdir() if path.is_dir()):
        loaded = load_layer(child, layer_name, source_type="corp")
        if loaded.config.identifier in layers:
            raise ValidationError(f"Duplicate {layer_name} id {loaded.config.identifier}")
        layers[loaded.config.identifier] = loaded
    return layers


def load_layer(path: Path, layer_name: str, source_type: str) -> LayerData:
    config_path = path / "config.toml"
    raw = read_toml(config_path)
    identifier = str(raw.get("id") or raw.get("repo_id") or raw.get("org_id") or path.name)
    config = LayerConfig(
        layer_name=layer_name,
        layer_path=path,
        identifier=identifier,
        owner=_optional_str(raw.get("owner")),
        maintainer=_optional_str(raw.get("maintainer")),
        lifecycle_status=parse_lifecycle_status(raw.get("status"), config_path),
        review_status=parse_review_status(raw.get("review_status"), config_path),
        deprecated_by=_optional_str(raw.get("deprecated_by")),
        sunset_after=_optional_str(raw.get("sunset_after")),
        stop_conditions=_str_list(raw.get("stop_conditions")),
        intended_consumers=_str_list(raw.get("intended_consumers")),
        context_quality_max_active_items=_optional_int(raw.get("context_quality_max_active_items")),
        enabled_sources=_str_list(raw.get("enabled_sources")),
        disabled_sources=_str_list(raw.get("disabled_sources")),
        enabled_skills=_config_list(raw, "skills", "enabled", "enabled_skills"),
        disabled_skills=_config_list(raw, "skills", "disabled", "disabled_skills"),
        recommended_skills=_config_list(raw, "skills", "recommended", "recommended_skills"),
        baseline_policies=_config_list(raw, "policies", "required", "baseline_policies"),
        optional_policies=_config_list(raw, "policies", "enabled", "optional_policies"),
        disabled_optional_policies=_config_list(raw, "policies", "disabled", "disabled_optional_policies"),
        recommended_policies=_config_list(raw, "policies", "recommended", "recommended_policies"),
        contexts=_config_list(raw, "contexts", "enabled", "contexts"),
        disabled_contexts=_config_list(raw, "contexts", "disabled", "disabled_contexts"),
        recommended_contexts=_config_list(raw, "contexts", "recommended", "recommended_contexts"),
        required_completion_gates=_config_list(raw, "completion_gates", "required", "required_completion_gates"),
        optional_completion_gates=_config_list(raw, "completion_gates", "enabled", "optional_completion_gates"),
        disabled_optional_completion_gates=_config_list(raw, "completion_gates", "disabled", "disabled_optional_completion_gates"),
        recommended_completion_gates=_config_list(raw, "completion_gates", "recommended", "recommended_completion_gates"),
        required_packs=_config_list(raw, "packs", "required", "required_packs"),
        enabled_packs=_config_list(raw, "packs", "enabled", "enabled_packs"),
        disabled_packs=_config_list(raw, "packs", "disabled", "disabled_packs"),
        recommended_packs=_config_list(raw, "packs", "recommended", "recommended_packs"),
        enabled_playbooks=_config_list(raw, "playbooks", "enabled", "enabled_playbooks"),
        disabled_playbooks=_config_list(raw, "playbooks", "disabled", "disabled_playbooks"),
        recommended_playbooks=_config_list(raw, "playbooks", "recommended", "recommended_playbooks"),
        enabled_profiles=_config_list(raw, "profiles", "enabled", "enabled_profiles"),
        disabled_profiles=_config_list(raw, "profiles", "disabled", "disabled_profiles"),
        recommended_profiles=_config_list(raw, "profiles", "recommended", "recommended_profiles"),
        recommended_agent_types=_str_list(raw.get("recommended_agent_types", raw.get("preferred_agent_types"))),
        allowed_profiles=_str_list(raw.get("allowed_profiles")),
        default_profile=raw.get("default_profile"),
        languages=_str_list(raw.get("languages")),
        frameworks=_str_list(raw.get("frameworks")),
        framework_versions=_str_dict(raw.get("framework_versions")),
        repo_tags=_str_list(raw.get("repo_tags")),
        item_overrides=parse_item_overrides(raw.get("item_override", []), config_path),
        normalized_remotes=_str_list(raw.get("normalized_remotes")),
        repo_group_id=raw.get("repo_group_id"),
        repo_class=raw.get("repo_class"),
        minimal_enabled_skills=_str_list(raw.get("minimal_enabled_skills")),
        minimal_optional_policies=_str_list(raw.get("minimal_optional_policies")),
        minimal_contexts=_str_list(raw.get("minimal_contexts")),
        protected_fields=set(_str_list(raw.get("protected_fields"))),
    )
    apply_generalized_activation(config, raw, config_path)
    validate_layer_config(config, config_path)
    items = load_items(path, source_type=source_type, source_namespace=identifier)
    profiles = load_profile_configs(path)
    return LayerData(config=config, items=items, profiles=profiles)


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
            owner=_optional_str(raw.get("owner")),
            maintainer=_optional_str(raw.get("maintainer")),
            lifecycle_status=parse_lifecycle_status(raw.get("status"), profile_path),
            review_status=parse_review_status(raw.get("review_status"), profile_path),
            deprecated_by=_optional_str(raw.get("deprecated_by")),
            sunset_after=_optional_str(raw.get("sunset_after")),
            stop_conditions=_str_list(raw.get("stop_conditions")),
            intended_consumers=_str_list(raw.get("intended_consumers")),
            context_quality_max_active_items=_optional_int(raw.get("context_quality_max_active_items")),
            enabled_skills=_config_list(raw, "skills", "enabled", "enabled_skills"),
            disabled_skills=_config_list(raw, "skills", "disabled", "disabled_skills"),
            recommended_skills=_config_list(raw, "skills", "recommended", "recommended_skills"),
            baseline_policies=_config_list(raw, "policies", "required", "baseline_policies"),
            optional_policies=_config_list(raw, "policies", "enabled", "optional_policies"),
            disabled_optional_policies=_config_list(raw, "policies", "disabled", "disabled_optional_policies"),
            recommended_policies=_config_list(raw, "policies", "recommended", "recommended_policies"),
            contexts=_config_list(raw, "contexts", "enabled", "contexts"),
            disabled_contexts=_config_list(raw, "contexts", "disabled", "disabled_contexts"),
            recommended_contexts=_config_list(raw, "contexts", "recommended", "recommended_contexts"),
            required_completion_gates=_config_list(raw, "completion_gates", "required", "required_completion_gates"),
            optional_completion_gates=_config_list(raw, "completion_gates", "enabled", "optional_completion_gates"),
            disabled_optional_completion_gates=_config_list(raw, "completion_gates", "disabled", "disabled_optional_completion_gates"),
            recommended_completion_gates=_config_list(raw, "completion_gates", "recommended", "recommended_completion_gates"),
            required_packs=_config_list(raw, "packs", "required", "required_packs"),
            enabled_packs=_config_list(raw, "packs", "enabled", "enabled_packs"),
            disabled_packs=_config_list(raw, "packs", "disabled", "disabled_packs"),
            recommended_packs=_config_list(raw, "packs", "recommended", "recommended_packs"),
            enabled_playbooks=_config_list(raw, "playbooks", "enabled", "enabled_playbooks"),
            disabled_playbooks=_config_list(raw, "playbooks", "disabled", "disabled_playbooks"),
            recommended_playbooks=_config_list(raw, "playbooks", "recommended", "recommended_playbooks"),
            enabled_profiles=_config_list(raw, "profiles", "enabled", "enabled_profiles"),
            disabled_profiles=_config_list(raw, "profiles", "disabled", "disabled_profiles"),
            recommended_profiles=_config_list(raw, "profiles", "recommended", "recommended_profiles"),
            recommended_agent_types=_str_list(raw.get("recommended_agent_types", raw.get("preferred_agent_types"))),
            languages=_str_list(raw.get("languages")),
            frameworks=_str_list(raw.get("frameworks")),
            framework_versions=_str_dict(raw.get("framework_versions")),
            repo_tags=_str_list(raw.get("repo_tags")),
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
    for item_id in _str_list(activation.get("required")):
        add_activation_id(config, item_id, "required", config_path)
    for item_id in _str_list(activation.get("enabled")):
        add_activation_id(config, item_id, "enabled", config_path)
    for item_id in _str_list(activation.get("disabled")):
        add_activation_id(config, item_id, "disabled", config_path)
    for item_id in _str_list(activation.get("recommended")):
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


def load_items(
    layer_root: Path,
    source_type: str,
    source_namespace: str,
    *,
    allow_native_source_formats: bool = False,
) -> dict[str, Item]:
    items: dict[str, Item] = {}
    for kind, folder in VALID_KINDS.items():
        base = layer_root / folder
        if not base.exists():
            continue
        for item_dir in sorted(path for path in base.iterdir() if path.is_dir()):
            if allow_native_source_formats and not (item_dir / "item.toml").exists():
                continue
            item = load_item(item_dir, kind, source_type, source_namespace)
            if item.item_id in items:
                raise ValidationError(f"Duplicate canonical id in layer {layer_root}: {item.item_id}")
            items[item.item_id] = item
    if allow_native_source_formats:
        for item in load_claude_native_items(layer_root, source_type, source_namespace).values():
            if item.item_id in items:
                raise ValidationError(f"Duplicate canonical id in layer {layer_root}: {item.item_id}")
            items[item.item_id] = item
        for item in load_cursor_native_items(layer_root, source_type, source_namespace).values():
            if item.item_id in items:
                raise ValidationError(f"Duplicate canonical id in layer {layer_root}: {item.item_id}")
            items[item.item_id] = item
    return items


def load_item(item_dir: Path, expected_kind: str, source_type: str, source_namespace: str) -> Item:
    item_path = item_dir / "item.toml"
    raw = read_toml(item_path)
    validate_item_toml(raw, item_path)
    kind = str(raw.get("kind", ""))
    if kind != expected_kind:
        raise ValidationError(f"{item_dir} declared kind {kind!r}; expected {expected_kind!r}")
    item_id = str(raw.get("id", ""))
    if not item_id:
        raise ValidationError(f"{item_dir} missing item id")
    parts = validate_canonical_id(item_id, expected_kind=expected_kind, path=item_dir)
    privacy = str(raw.get("privacy", ""))
    if privacy not in VALID_PRIVACY:
        raise ValidationError(f"Invalid privacy {privacy!r} in {item_dir}")
    activation_required, activation_enabled = parse_pack_item_activation(raw, kind, item_path)
    source_note = raw.get("source_note")
    trust_level = parse_trust_level(raw, source_type, source_note, item_path)
    allows_scripts = bool(raw.get("allows_scripts", False))
    if allows_scripts:
        raise ValidationError(f"allows_scripts = true is not supported in v1: {item_path}")
    body_path = item_dir / "body.md"
    if not body_path.exists():
        raise ValidationError(f"Missing body.md for {item_id} at {item_dir}")
    item = Item(
        item_id=item_id,
        kind=kind,
        title=str(raw["title"]),
        privacy=privacy,
        source_type=source_type,
        source_namespace=source_namespace,
        source_ref=str(raw.get("source_ref", layer_root_ref(item_dir))),
        body=body_path.read_text(encoding="utf-8"),
        slug=parts[3],
        item_path=item_path,
        body_path=body_path,
        owner=_optional_str(raw.get("owner")),
        maintainer=_optional_str(raw.get("maintainer")),
        lifecycle_status=parse_lifecycle_status(raw.get("status"), item_path),
        review_status=parse_review_status(raw.get("review_status"), item_path),
        deprecated_by=_optional_str(raw.get("deprecated_by")),
        sunset_after=_optional_str(raw.get("sunset_after")),
        stop_conditions=_str_list(raw.get("stop_conditions")),
        tags=_str_list(raw.get("tags")),
        recommended_agent_types=_str_list(raw.get("recommended_agent_types")),
        timeout_seconds=_optional_int(raw.get("timeout_seconds")),
        source_note=source_note,
        target_tools=_str_list(raw.get("target_tools")),
        claude_model=raw.get("claude_model"),
        cursor_globs=_str_list(raw.get("cursor_globs")),
        cursor_always_apply=raw.get("cursor_always_apply"),
        target_settings=parse_target_settings(raw.get("target", {}), item_path),
        policy_rules=list(raw.get("policy_rules", [])),
        usage_mode=str(raw.get("usage_mode", "reusable")),
        activation_required=activation_required,
        activation_enabled=activation_enabled,
        promotion_checklist=parse_promotion_checklist(raw.get("promotion_checklist"), kind, item_path),
        trust_level=trust_level,
        trust_level_explicit="trust_level" in raw,
        allows_scripts=allows_scripts,
        reviewed_by=_optional_str(raw.get("reviewed_by")),
        reviewed_at=_optional_str(raw.get("reviewed_at")),
        applies_to_languages=_str_list(raw.get("applies_to_languages")),
        applies_to_frameworks=_str_list(raw.get("applies_to_frameworks")),
        compatible_versions=_str_dict(raw.get("compatible_versions")),
        repo_tags=_str_list(raw.get("repo_tags")),
        inputs=parse_flow_list(raw.get("inputs"), kind, "inputs", item_path),
        outputs=parse_flow_list(raw.get("outputs"), kind, "outputs", item_path),
        evidence_required=parse_evidence_required(raw.get("evidence_required"), kind, item_path),
    )
    return item


def parse_trust_level(raw: dict[str, Any], source_type: str, source_note: Any, item_path: Path) -> str:
    if "trust_level" in raw:
        trust_level = str(raw["trust_level"])
        if trust_level not in VALID_TRUST_LEVELS:
            raise ValidationError(f"Invalid trust_level {trust_level!r} in {item_path}")
        return trust_level
    if source_type == "corp":
        return "corp-reviewed"
    if source_type == "user" and str(source_note or "").startswith("Imported from "):
        return "unreviewed"
    if source_type == "user":
        return "user-trusted"
    return "unreviewed"


def parse_lifecycle_status(value: Any, item_path: Path) -> str:
    status = str(value or "active")
    if status not in VALID_LIFECYCLE_STATUSES:
        raise ValidationError(f"Invalid status {status!r} in {item_path}")
    return status


def parse_review_status(value: Any, item_path: Path) -> str:
    status = str(value or "unreviewed")
    if status not in VALID_REVIEW_STATUSES:
        raise ValidationError(f"Invalid review_status {status!r} in {item_path}")
    return status


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_promotion_checklist(value: Any, kind: str, item_path: Path) -> dict[str, str]:
    if value is None:
        return {}
    if kind != "skill":
        raise ValidationError(f"promotion_checklist is only supported for skill items: {item_path}")
    if not isinstance(value, dict):
        raise ValidationError(f"promotion_checklist must be a TOML table in {item_path}")
    checklist: dict[str, str] = {}
    for key, raw_value in value.items():
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValidationError(f"promotion_checklist.{key} must be a non-empty string in {item_path}")
        checklist[str(key)] = raw_value.strip()
    return checklist


def parse_evidence_required(value: Any, kind: str, item_path: Path) -> list[str]:
    if value is None:
        return []
    if kind not in {"completion_gate", "playbook"}:
        raise ValidationError(f"evidence_required is only supported for completion gate and playbook items: {item_path}")
    return _str_list(value)


def parse_flow_list(value: Any, kind: str, field_name: str, item_path: Path) -> list[str]:
    if value is None:
        return []
    if kind != "playbook":
        raise ValidationError(f"{field_name} is only supported for playbook items: {item_path}")
    return _str_list(value)


def parse_pack_item_activation(raw: dict[str, Any], kind: str, item_path: Path) -> tuple[list[str], list[str]]:
    activation = raw.get("activation")
    if activation is None:
        return [], []
    if kind != "pack":
        raise ValidationError(f"[activation] in item.toml is only supported for pack items: {item_path}")
    if not isinstance(activation, dict):
        raise ValidationError(f"[activation] must be a table in {item_path}")
    unknown = set(activation) - {"required", "enabled"}
    if unknown:
        raise ValidationError(f"Unsupported pack activation fields in {item_path}: {', '.join(sorted(unknown))}")
    required = _str_list(activation.get("required"))
    enabled = _str_list(activation.get("enabled"))
    for mode, item_ids in [("required", required), ("enabled", enabled)]:
        for item_id in item_ids:
            _, _, ref_kind, _ = validate_canonical_id(item_id, path=item_path)
            if ref_kind == "profile":
                raise ValidationError(f"Pack activation.{mode} cannot reference profile items in {item_path}: {item_id}")
            if mode == "required" and ref_kind not in {"policy", "completion_gate", "pack"}:
                raise ValidationError(f"Pack activation.required does not support {ref_kind} items in {item_path}: {item_id}")
    return required, enabled


def layer_root_ref(path: Path) -> str:
    return str(path.parent.parent)


def load_claude_native_items(layer_root: Path, source_type: str, source_namespace: str) -> dict[str, Item]:
    items: dict[str, Item] = {}
    for skill_md in iter_claude_native_skill_files(layer_root):
        slug = skill_md.parent.name
        raw_text = skill_md.read_text(encoding="utf-8")
        metadata, _ = parse_frontmatter_document(raw_text, skill_md)
        name = str(metadata.get("name") or "").strip()
        if not name:
            raise ValidationError(f"Claude-native skill is missing required frontmatter field 'name' in {skill_md}")
        tools = metadata.get("tools", [])
        if tools and not isinstance(tools, list):
            raise ValidationError(f"Claude-native frontmatter field 'tools' must be a list in {skill_md}")
        item_id = f"{source_type}.{source_namespace}.skill.{slug}"
        items[item_id] = Item(
            item_id=item_id,
            kind="skill",
            title=name,
            privacy="repo-safe",
            source_type=source_type,
            source_namespace=source_namespace,
            source_ref=str(layer_root),
            body=raw_text,
            slug=slug,
            item_path=skill_md,
            body_path=skill_md,
            target_tools=[str(tool) for tool in tools],
            claude_model=str(metadata["model"]) if metadata.get("model") else None,
            usage_mode=str(metadata.get("usage_mode", "reusable")),
            trust_level=parse_trust_level({}, source_type, None, skill_md),
        )
    return items


def iter_claude_native_skill_files(layer_root: Path) -> list[Path]:
    seen: set[Path] = set()
    skill_files: list[Path] = []

    def add(skill_md: Path) -> None:
        resolved = skill_md.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        skill_files.append(skill_md)

    for skill_dir in sorted(path for path in layer_root.iterdir() if path.is_dir() and not path.name.startswith(".")):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            add(skill_md)

    for relative_root in ("skills", ".claude/skills", ".agents/skills"):
        native_root = layer_root / relative_root
        if not native_root.exists():
            continue
        for skill_md in sorted(native_root.rglob("SKILL.md")):
            if any(part == "deprecated" for part in skill_md.relative_to(native_root).parts):
                continue
            add(skill_md)

    return skill_files


def load_cursor_native_items(layer_root: Path, source_type: str, source_namespace: str) -> dict[str, Item]:
    items: dict[str, Item] = {}
    rules_root = layer_root / ".cursor" / "rules"
    if not rules_root.exists():
        return items
    for path in sorted(rules_root.glob("*.mdc")):
        raw_text = path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter_document(raw_text, path)
        description = str(metadata.get("description") or "").strip()
        if not description:
            raise ValidationError(f"Cursor-native rule is missing required frontmatter field 'description' in {path}")
        globs = metadata.get("globs", [])
        if globs and not isinstance(globs, list):
            raise ValidationError(f"Cursor-native frontmatter field 'globs' must be a list in {path}")
        always_apply = metadata.get("alwaysApply")
        if always_apply is not None and not isinstance(always_apply, bool):
            raise ValidationError(f"Cursor-native frontmatter field 'alwaysApply' must be a boolean in {path}")
        slug = path.stem
        item_id = f"{source_type}.{source_namespace}.skill.{slug}"
        items[item_id] = Item(
            item_id=item_id,
            kind="skill",
            title=slug.replace("-", " ").title(),
            privacy="repo-safe",
            source_type=source_type,
            source_namespace=source_namespace,
            source_ref=str(layer_root),
            body=body.strip() + "\n",
            slug=slug,
            item_path=path,
            body_path=path,
            target_tools=["cursor"],
            cursor_globs=[str(glob) for glob in globs],
            cursor_always_apply=always_apply,
            source_note=description,
            usage_mode=str(metadata.get("usage_mode", "reusable")),
            trust_level=parse_trust_level({}, source_type, description, path),
        )
    return items


def load_source_registry(root: Path) -> dict[str, SourceDefinition]:
    indexes = read_toml(root / "indexes" / "sources.toml")
    sources: dict[str, SourceDefinition] = {}
    for entry in indexes.get("source", []):
        source_path = root / str(entry["path"])
        source = load_source_manifest(source_path, source_type="external")
        if source.source_id in sources:
            raise ValidationError(f"Duplicate source id {source.source_id}")
        sources[source.source_id] = source
    return sources


def load_source_manifest(path: Path, source_type: str) -> SourceDefinition:
    raw = read_toml(path)
    required = ["id", "url", "commit", "namespace", "trust_mode"]
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValidationError(f"Source manifest {path} missing keys: {', '.join(missing)}")
    source_id = str(raw["id"])
    commit = str(raw["commit"])
    namespace = str(raw["namespace"])
    trust_level = _optional_str(raw.get("trust_level"))
    validate_source_id(source_id, path)
    validate_commit_hash(commit, path)
    if not namespace:
        raise ValidationError(f"Source namespace must be non-empty in {path}")
    if trust_level is not None and trust_level not in VALID_TRUST_LEVELS:
        raise ValidationError(f"Invalid trust_level {trust_level!r} in {path}")
    return SourceDefinition(
        source_id=source_id,
        url=str(raw["url"]),
        commit=commit,
        namespace=namespace,
        trust_mode=str(raw["trust_mode"]),
        fingerprint=raw.get("fingerprint"),
        path=path,
        source_type=source_type,
        trust_level=trust_level,
    )


def load_personal_sources(source_dir: Path) -> dict[str, SourceDefinition]:
    if not source_dir.exists():
        return {}
    sources: dict[str, SourceDefinition] = {}
    for path in sorted(source_dir.glob("*.toml")):
        source = load_source_manifest(path, source_type="user")
        if source.source_id in sources:
            raise ValidationError(f"Duplicate personal source id {source.source_id}")
        sources[source.source_id] = source
    return sources


def validate_repo_indexes(
    root: Path,
    repo_groups: dict[str, LayerData],
    repos: dict[str, LayerData],
    sources: dict[str, SourceDefinition],
) -> None:
    repo_index = read_toml(root / "indexes" / "repos.toml")
    group_index = read_toml(root / "indexes" / "repo-groups.toml")
    indexed_repos = {entry["id"]: root / str(entry["path"]) for entry in repo_index.get("repo", [])}
    indexed_groups = {entry["id"]: root / str(entry["path"]) for entry in group_index.get("repo_group", [])}
    indexed_sources = {entry["id"] for entry in read_toml(root / "indexes" / "sources.toml").get("source", [])}
    if set(indexed_repos) != set(repos):
        raise ValidationError("Repo index disagrees with repo folder truth")
    if set(indexed_groups) != set(repo_groups):
        raise ValidationError("Repo-group index disagrees with repo-group folder truth")
    if indexed_sources != set(sources):
        raise ValidationError("Source index disagrees with source folder truth")
    for repo_id, layer in repos.items():
        if indexed_repos[repo_id].resolve() != layer.config.layer_path.resolve():
            raise ValidationError(f"Repo index path mismatch for {repo_id}")
    for group_id, layer in repo_groups.items():
        if indexed_groups[group_id].resolve() != layer.config.layer_path.resolve():
            raise ValidationError(f"Repo-group index path mismatch for {group_id}")


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
                timeout_seconds=_optional_int(entry.get("timeout_seconds")),
                recommended_agent_types=_str_list(entry.get("recommended_agent_types")),
                tags=_str_list(entry.get("tags")),
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
                disabled_skills=_str_list(entry.get("disabled_skills")),
            )
        )
    return bindings


def parse_target_settings(raw: Any, item_path: Path) -> dict[str, TargetSettings]:
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ValidationError(f"target settings must be a table in {item_path}")
    result: dict[str, TargetSettings] = {}
    for target, settings in raw.items():
        if target not in {"claude", "codex", "cursor"}:
            raise ValidationError(f"Unsupported target {target!r} in {item_path}")
        if not isinstance(settings, dict):
            raise ValidationError(f"target.{target} must be a table in {item_path}")
        unknown = set(settings) - {"mode", "include", "summary_budget", "globs", "always_apply"}
        if unknown:
            raise ValidationError(f"Unsupported target.{target} fields in {item_path}: {', '.join(sorted(unknown))}")
        include = settings.get("include", True)
        if not isinstance(include, bool):
            raise ValidationError(f"target.{target}.include must be a boolean in {item_path}")
        always_apply = settings.get("always_apply")
        if always_apply is not None and not isinstance(always_apply, bool):
            raise ValidationError(f"target.{target}.always_apply must be a boolean in {item_path}")
        result[target] = TargetSettings(
            mode=str(settings["mode"]) if settings.get("mode") is not None else None,
            include=include,
            summary_budget=str(settings["summary_budget"]) if settings.get("summary_budget") is not None else None,
            globs=_str_list(settings.get("globs")),
            always_apply=always_apply,
        )
    return result


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"Expected list, got {type(value).__name__}")
    return [str(item) for item in value]


def _str_dict(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(f"Expected table, got {type(value).__name__}")
    return {str(key): str(item) for key, item in value.items()}


def _config_list(raw: dict[str, Any], section: str, key: str, flat_key: str) -> list[str]:
    nested = raw.get(section)
    if isinstance(nested, dict) and key in nested:
        return _str_list(nested.get(key))
    return _str_list(raw.get(flat_key))


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


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
