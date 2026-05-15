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
    *,
    allow_parallel_pin: bool = False,
    update_existing_source_id: str | None = None,
) -> Path:
    existing = _load_existing_source_manifests(corp_root / "org" / "sources")
    _validate_parallel_pin_choice(
        source_id=source_id,
        url=url,
        commit=commit,
        existing=existing,
        allow_parallel_pin=allow_parallel_pin,
        update_existing_source_id=update_existing_source_id,
    )
    if update_existing_source_id:
        if source_id != update_existing_source_id:
            raise ValidationError("--source-id must match --update-existing-source-id when updating an existing source pin")
        manifest_path = corp_root / "org" / "sources" / f"{update_existing_source_id}.toml"
        if not manifest_path.exists():
            raise ValidationError(f"Existing source id not found: {update_existing_source_id}")
        write_simple_toml(manifest_path, _source_manifest_payload(source_id, url, commit, namespace, trust_mode))
        return manifest_path
    manifest_path = corp_root / "org" / "sources" / f"{source_id}.toml"
    if manifest_path.exists():
        raise ValidationError(f"Corp source manifest already exists: {manifest_path}")
    write_simple_toml(manifest_path, _source_manifest_payload(source_id, url, commit, namespace, trust_mode))
    update_source_index(corp_root / "indexes" / "sources.toml", source_id, f"org/sources/{source_id}.toml")
    return manifest_path


def register_user_source(
    user_root: Path,
    source_id: str,
    url: str,
    commit: str,
    namespace: str,
    trust_mode: str = "pinned-commit",
    *,
    allow_parallel_pin: bool = False,
    update_existing_source_id: str | None = None,
) -> Path:
    existing = _load_existing_source_manifests(user_root / "sources")
    _validate_parallel_pin_choice(
        source_id=source_id,
        url=url,
        commit=commit,
        existing=existing,
        allow_parallel_pin=allow_parallel_pin,
        update_existing_source_id=update_existing_source_id,
    )
    if update_existing_source_id:
        if source_id != update_existing_source_id:
            raise ValidationError("--source-id must match --update-existing-source-id when updating an existing source pin")
        manifest_path = user_root / "sources" / f"{update_existing_source_id}.toml"
        if not manifest_path.exists():
            raise ValidationError(f"Existing source id not found: {update_existing_source_id}")
        write_simple_toml(manifest_path, _source_manifest_payload(source_id, url, commit, namespace, trust_mode))
        return manifest_path
    manifest_path = user_root / "sources" / f"{source_id}.toml"
    if manifest_path.exists():
        raise ValidationError(f"User source manifest already exists: {manifest_path}")
    write_simple_toml(manifest_path, _source_manifest_payload(source_id, url, commit, namespace, trust_mode))
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


def _source_manifest_payload(source_id: str, url: str, commit: str, namespace: str, trust_mode: str) -> dict[str, str]:
    return {
        "id": source_id,
        "url": url,
        "commit": commit,
        "namespace": namespace,
        "trust_mode": trust_mode,
    }


def _load_existing_source_manifests(source_dir: Path) -> list[dict[str, str]]:
    if not source_dir.exists():
        return []
    manifests: list[dict[str, str]] = []
    for path in sorted(source_dir.glob("*.toml")):
        raw = read_toml(path)
        manifests.append(
            {
                "id": str(raw.get("id", "")),
                "url": str(raw.get("url", "")),
                "commit": str(raw.get("commit", "")),
            }
        )
    return manifests


def _validate_parallel_pin_choice(
    *,
    source_id: str,
    url: str,
    commit: str,
    existing: list[dict[str, str]],
    allow_parallel_pin: bool,
    update_existing_source_id: str | None,
) -> None:
    conflicts = [entry for entry in existing if entry["url"] == url and entry["commit"] != commit]
    if not conflicts:
        return
    if update_existing_source_id:
        if update_existing_source_id not in {entry["id"] for entry in conflicts}:
            raise ValidationError(
                f"Requested source id {update_existing_source_id} is not one of the existing pin tracks for {url}: "
                + ", ".join(sorted(entry["id"] for entry in conflicts))
            )
        return
    if allow_parallel_pin:
        return
    conflict_text = ", ".join(f"{entry['id']}@{entry['commit']}" for entry in sorted(conflicts, key=lambda entry: entry["id"]))
    raise ValidationError(
        f"Source URL {url} is already approved at another pin: {conflict_text}. "
        "Use --update-existing-source-id to move an existing pin track or --allow-parallel-pin to create a second track."
    )
