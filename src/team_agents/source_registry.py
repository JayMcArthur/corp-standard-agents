from __future__ import annotations

import tomllib
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.toml_utils import read_toml, write_simple_toml, write_toml_document


def register_corp_source(
    corp_root: Path,
    source_id: str,
    url: str,
    commit: str,
    namespace: str,
    trust_mode: str = "pinned-commit",
) -> Path:
    manifest_path = corp_root / "org" / "sources" / f"{source_id}.toml"
    if manifest_path.exists():
        raise ValidationError(f"Corp source manifest already exists: {manifest_path}")
    write_simple_toml(
        manifest_path,
        {
            "id": source_id,
            "url": url,
            "commit": commit,
            "namespace": namespace,
            "trust_mode": trust_mode,
        },
    )
    update_source_index(corp_root / "indexes" / "sources.toml", source_id, f"org/sources/{source_id}.toml")
    return manifest_path


def register_user_source(
    user_root: Path,
    source_id: str,
    url: str,
    commit: str,
    namespace: str,
    trust_mode: str = "pinned-commit",
) -> Path:
    manifest_path = user_root / "sources" / f"{source_id}.toml"
    if manifest_path.exists():
        raise ValidationError(f"User source manifest already exists: {manifest_path}")
    write_simple_toml(
        manifest_path,
        {
            "id": source_id,
            "url": url,
            "commit": commit,
            "namespace": namespace,
            "trust_mode": trust_mode,
        },
    )
    return manifest_path


def enable_source_in_layer(layer_root: Path, source_id: str) -> Path:
    config_path = layer_root / "config.toml"
    data = read_toml(config_path)
    enabled = _str_list(data.get("enabled_sources"))
    if source_id not in enabled:
        enabled.append(source_id)
    disabled = [item for item in _str_list(data.get("disabled_sources")) if item != source_id]
    data["enabled_sources"] = sorted(enabled)
    data["disabled_sources"] = sorted(disabled)
    write_toml_document(config_path, data)
    return config_path


def update_source_index(index_path: Path, source_id: str, source_path: str) -> None:
    existing = []
    if index_path.exists() and index_path.read_text(encoding="utf-8").strip():
        data = tomllib.loads(index_path.read_text(encoding="utf-8"))
        existing = data.get("source", [])
    if any(entry.get("id") == source_id for entry in existing):
        raise ValidationError(f"Source index already contains id {source_id}")
    existing.append({"id": source_id, "path": source_path})
    existing.sort(key=lambda entry: str(entry["id"]))
    write_toml_document(index_path, {"source": existing})


def resolve_layer_root(
    corp_root: Path,
    user_root: Path,
    layer: str,
    repo_id: str | None = None,
) -> Path:
    if layer == "user":
        return user_root
    if layer == "org":
        return corp_root / "org"
    if layer == "repo":
        if not repo_id:
            raise ValidationError("repo layer requires repo_id")
        return corp_root / "repos" / repo_id
    raise ValidationError(f"Unsupported layer {layer!r}")


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
