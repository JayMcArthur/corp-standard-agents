from __future__ import annotations

from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.loading_parsing import VALID_TRUST_LEVELS, optional_str
from team_agents.models import LayerData, SourceDefinition
from team_agents.toml_utils import read_toml
from team_agents.validation import validate_commit_hash, validate_source_id


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
    trust_level = optional_str(raw.get("trust_level"))
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
