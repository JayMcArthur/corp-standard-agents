from __future__ import annotations

from pathlib import Path
from typing import Any

from team_agents.errors import ValidationError

VALID_LIFECYCLE_STATUSES = {"draft", "active", "deprecated", "archived"}
VALID_REVIEW_STATUSES = {"unreviewed", "reviewed", "approved"}
VALID_TRUST_LEVELS = {"unreviewed", "user-trusted", "corp-reviewed", "corp-required"}


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


def optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"Expected list, got {type(value).__name__}")
    return [str(item) for item in value]


def str_dict(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(f"Expected table, got {type(value).__name__}")
    return {str(key): str(item) for key, item in value.items()}


def config_list(raw: dict[str, Any], section: str, key: str, flat_key: str) -> list[str]:
    nested = raw.get(section)
    if isinstance(nested, dict) and key in nested:
        return str_list(nested.get(key))
    return str_list(raw.get(flat_key))
