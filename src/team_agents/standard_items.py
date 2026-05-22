from __future__ import annotations

from pathlib import Path
from typing import Any

from team_agents.errors import ValidationError
from team_agents.item_schema import validate_item_toml
from team_agents.loading_parsing import (
    VALID_TRUST_LEVELS,
    optional_int,
    optional_str,
    parse_lifecycle_status,
    parse_review_status,
    str_dict,
    str_list,
)
from team_agents.models import Item, TargetSettings
from team_agents.source_adapters import (
    load_claude_native_items as load_claude_native_source_items,
    load_cursor_native_items as load_cursor_native_source_items,
)
from team_agents.toml_utils import read_toml
from team_agents.validation import validate_canonical_id


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
        for item in load_claude_native_source_items(
            layer_root,
            source_type,
            source_namespace,
            trust_level_for=parse_trust_level,
        ).values():
            if item.item_id in items:
                raise ValidationError(f"Duplicate canonical id in layer {layer_root}: {item.item_id}")
            items[item.item_id] = item
        for item in load_cursor_native_source_items(
            layer_root,
            source_type,
            source_namespace,
            trust_level_for=parse_trust_level,
        ).values():
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
    return Item(
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
        owner=optional_str(raw.get("owner")),
        maintainer=optional_str(raw.get("maintainer")),
        lifecycle_status=parse_lifecycle_status(raw.get("status"), item_path),
        review_status=parse_review_status(raw.get("review_status"), item_path),
        deprecated_by=optional_str(raw.get("deprecated_by")),
        sunset_after=optional_str(raw.get("sunset_after")),
        stop_conditions=str_list(raw.get("stop_conditions")),
        tags=str_list(raw.get("tags")),
        recommended_agent_types=str_list(raw.get("recommended_agent_types")),
        timeout_seconds=optional_int(raw.get("timeout_seconds")),
        source_note=source_note,
        target_tools=str_list(raw.get("target_tools")),
        claude_model=raw.get("claude_model"),
        cursor_globs=str_list(raw.get("cursor_globs")),
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
        reviewed_by=optional_str(raw.get("reviewed_by")),
        reviewed_at=optional_str(raw.get("reviewed_at")),
        applies_to_languages=str_list(raw.get("applies_to_languages")),
        applies_to_frameworks=str_list(raw.get("applies_to_frameworks")),
        compatible_versions=str_dict(raw.get("compatible_versions")),
        repo_tags=str_list(raw.get("repo_tags")),
        inputs=parse_flow_list(raw.get("inputs"), kind, "inputs", item_path),
        outputs=parse_flow_list(raw.get("outputs"), kind, "outputs", item_path),
        evidence_required=parse_evidence_required(raw.get("evidence_required"), kind, item_path),
    )


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
    return str_list(value)


def parse_flow_list(value: Any, kind: str, field_name: str, item_path: Path) -> list[str]:
    if value is None:
        return []
    if kind != "playbook":
        raise ValidationError(f"{field_name} is only supported for playbook items: {item_path}")
    return str_list(value)


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
    required = str_list(activation.get("required"))
    enabled = str_list(activation.get("enabled"))
    for mode, item_ids in [("required", required), ("enabled", enabled)]:
        for item_id in item_ids:
            _, _, ref_kind, _ = validate_canonical_id(item_id, path=item_path)
            if ref_kind == "profile":
                raise ValidationError(f"Pack activation.{mode} cannot reference profile items in {item_path}: {item_id}")
            if mode == "required" and ref_kind not in {"policy", "completion_gate", "pack"}:
                raise ValidationError(f"Pack activation.required does not support {ref_kind} items in {item_path}: {item_id}")
    return required, enabled


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
            globs=str_list(settings.get("globs")),
            always_apply=always_apply,
        )
    return result


def layer_root_ref(path: Path) -> str:
    return str(path.parent.parent)
