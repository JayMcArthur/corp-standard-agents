from __future__ import annotations

import re
from pathlib import Path

from team_agents.errors import ValidationError


CANONICAL_ID_RE = re.compile(
    r"^(corp|external|user)\.([a-z0-9][a-z0-9_-]*)\.(skill|policy|context|completion_gate|playbook|pack|profile)\.([a-z0-9][a-z0-9_-]*)$"
)
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
REPO_CLASS_VALUES = {"client", "internal"}


def validate_canonical_id(item_id: str, expected_kind: str | None = None, path: Path | None = None) -> tuple[str, str, str, str]:
    match = CANONICAL_ID_RE.fullmatch(item_id)
    if not match:
        location = f" in {path}" if path else ""
        raise ValidationError(f"Invalid canonical id {item_id!r}{location}")
    source_type, namespace, kind, slug = match.groups()
    if expected_kind is not None and kind != expected_kind:
        location = f" in {path}" if path else ""
        raise ValidationError(f"Canonical id kind mismatch for {item_id!r}{location}; expected {expected_kind!r}")
    return source_type, namespace, kind, slug


def validate_source_id(source_id: str, path: Path) -> None:
    if not SOURCE_ID_RE.fullmatch(source_id):
        raise ValidationError(f"Invalid source id {source_id!r} in {path}")


def validate_commit_hash(commit: str, path: Path) -> None:
    if not COMMIT_RE.fullmatch(commit):
        raise ValidationError(f"Invalid commit hash {commit!r} in {path}")


def validate_repo_class(repo_class: str | None, path: Path) -> None:
    if repo_class is None:
        return
    if repo_class not in REPO_CLASS_VALUES:
        raise ValidationError(f"Invalid repo_class {repo_class!r} in {path}; expected one of {sorted(REPO_CLASS_VALUES)}")
