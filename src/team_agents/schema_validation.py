from __future__ import annotations

import re
from typing import Any

from team_agents.errors import ValidationError


def validate_schema_instance(
    instance: Any,
    schema: dict[str, Any],
    location: str = "$",
    root_schema: dict[str, Any] | None = None,
) -> None:
    if root_schema is None:
        root_schema = schema
    if "$ref" in schema:
        validate_schema_instance(instance, _resolve_ref(root_schema, schema["$ref"]), location, root_schema)
        return

    expected_type = schema.get("type")
    if expected_type is not None:
        _validate_type(instance, expected_type, location)

    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{location} must be one of {schema['enum']!r}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < int(schema["minLength"]):
            raise ValidationError(f"{location} must be at least {schema['minLength']} characters long")
        if "pattern" in schema and not re.fullmatch(str(schema["pattern"]), instance):
            raise ValidationError(f"{location} does not match required pattern")

    if _is_integer(instance) and "minimum" in schema and instance < int(schema["minimum"]):
        raise ValidationError(f"{location} must be >= {schema['minimum']}")

    if isinstance(instance, list) and "minItems" in schema and len(instance) < int(schema["minItems"]):
        raise ValidationError(f"{location} must contain at least {schema['minItems']} items")

    if _matches_type(expected_type, instance, "object"):
        _validate_object(instance, schema, location, root_schema)

    if _matches_type(expected_type, instance, "array"):
        item_schema = schema.get("items")
        if item_schema is None:
            return
        for index, value in enumerate(instance):
            validate_schema_instance(value, item_schema, f"{location}[{index}]", root_schema)


def _validate_object(instance: dict[str, Any], schema: dict[str, Any], location: str, root_schema: dict[str, Any]) -> None:
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    for key in required:
        if key not in instance:
            raise ValidationError(f"{location}.{key} is required")

    additional = schema.get("additionalProperties", True)
    extra_keys = set(instance) - set(properties)
    if additional is False and extra_keys:
        extras = ", ".join(sorted(extra_keys))
        raise ValidationError(f"{location} has unsupported properties: {extras}")
    if isinstance(additional, dict):
        for key in sorted(extra_keys):
            validate_schema_instance(instance[key], additional, f"{location}.{key}", root_schema)

    for key, value in instance.items():
        child_schema = properties.get(key)
        if child_schema is None:
            continue
        validate_schema_instance(value, child_schema, f"{location}.{key}", root_schema)


def _validate_type(instance: Any, expected_type: str | list[str], location: str) -> None:
    if isinstance(expected_type, list):
        if any(_matches_type(candidate, instance, candidate) for candidate in expected_type):
            return
        raise ValidationError(f"{location} must be one of the allowed types: {expected_type!r}")
    if not _matches_type(expected_type, instance, expected_type):
        raise ValidationError(f"{location} must be of type {expected_type}")


def _matches_type(expected_type: str | list[str] | None, instance: Any, candidate: str) -> bool:
    checks = {
        "array": isinstance(instance, list),
        "boolean": isinstance(instance, bool),
        "integer": _is_integer(instance),
        "null": instance is None,
        "object": isinstance(instance, dict),
        "string": isinstance(instance, str),
    }
    if candidate not in checks:
        raise ValidationError(f"Unsupported schema type {candidate!r}")
    return checks[candidate]


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValidationError(f"Unsupported schema ref {ref!r}")
    target: Any = root_schema
    for part in ref[2:].split("/"):
        target = target[part]
    if not isinstance(target, dict):
        raise ValidationError(f"Schema ref {ref!r} did not resolve to an object schema")
    return target
