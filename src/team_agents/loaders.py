from __future__ import annotations

from pathlib import Path
from typing import Any

from team_agents.errors import ValidationError
from team_agents.models import (
    CorpRepo,
    Item,
    ItemOverride,
    LayerConfig,
    LayerData,
    SourceDefinition,
    UserOverrides,
    WorkspaceBinding,
)
from team_agents.toml_utils import read_toml
from team_agents.validation import validate_canonical_id, validate_commit_hash, validate_repo_class, validate_source_id


VALID_KINDS = {"skill": "skills", "policy": "policies", "doc": "docs"}
VALID_PRIVACY = {"corp-private", "repo-safe"}
VALID_SOURCE_TYPES = {"corp", "external", "user"}
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


def load_user_overrides(root: Path) -> UserOverrides:
    root = root.resolve()
    if not root.exists():
        raise ValidationError(f"User override path does not exist: {root}")
    layer = load_layer(root, "user", source_type="user")
    data = read_toml(root / "config.toml")
    personal_sources = load_personal_sources(root / "sources")
    workspace_bindings = parse_workspace_bindings(data.get("workspace_binding", []), root)
    layer.config.workspace_bindings = workspace_bindings
    return UserOverrides(root=root, layer=layer, personal_sources=personal_sources, workspace_bindings=workspace_bindings)


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
        enabled_sources=_str_list(raw.get("enabled_sources")),
        disabled_sources=_str_list(raw.get("disabled_sources")),
        enabled_skills=_str_list(raw.get("enabled_skills")),
        disabled_skills=_str_list(raw.get("disabled_skills")),
        baseline_policies=_str_list(raw.get("baseline_policies")),
        optional_policies=_str_list(raw.get("optional_policies")),
        disabled_optional_policies=_str_list(raw.get("disabled_optional_policies")),
        docs=_str_list(raw.get("docs")),
        disabled_docs=_str_list(raw.get("disabled_docs")),
        recommended_agent_types=_str_list(raw.get("recommended_agent_types", raw.get("preferred_agent_types"))),
        item_overrides=parse_item_overrides(raw.get("item_override", []), config_path),
        normalized_remotes=_str_list(raw.get("normalized_remotes")),
        repo_group_id=raw.get("repo_group_id"),
        repo_class=raw.get("repo_class"),
        minimal_enabled_skills=_str_list(raw.get("minimal_enabled_skills")),
        minimal_optional_policies=_str_list(raw.get("minimal_optional_policies")),
        minimal_docs=_str_list(raw.get("minimal_docs")),
        protected_fields=set(_str_list(raw.get("protected_fields"))),
    )
    validate_layer_config(config, config_path)
    items = load_items(path, source_type=source_type, source_namespace=identifier)
    return LayerData(config=config, items=items)


def load_items(layer_root: Path, source_type: str, source_namespace: str) -> dict[str, Item]:
    items: dict[str, Item] = {}
    for kind, folder in VALID_KINDS.items():
        base = layer_root / folder
        if not base.exists():
            continue
        for item_dir in sorted(path for path in base.iterdir() if path.is_dir()):
            item = load_item(item_dir, kind, source_type, source_namespace)
            if item.item_id in items:
                raise ValidationError(f"Duplicate canonical id in layer {layer_root}: {item.item_id}")
            items[item.item_id] = item
    return items


def load_item(item_dir: Path, expected_kind: str, source_type: str, source_namespace: str) -> Item:
    raw = read_toml(item_dir / "item.toml")
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
    body_path = item_dir / "body.md"
    if not body_path.exists():
        raise ValidationError(f"Missing body.md for {item_id} at {item_dir}")
    item = Item(
        item_id=item_id,
        kind=kind,
        title=str(raw.get("title", item_dir.name)),
        privacy=privacy,
        source_type=source_type,
        source_namespace=source_namespace,
        source_ref=str(raw.get("source_ref", layer_root_ref(item_dir))),
        body=body_path.read_text(encoding="utf-8"),
        slug=parts[3],
        item_path=item_dir / "item.toml",
        body_path=body_path,
        tags=_str_list(raw.get("tags")),
        recommended_agent_types=_str_list(raw.get("recommended_agent_types")),
        timeout_seconds=_optional_int(raw.get("timeout_seconds")),
        source_note=raw.get("source_note"),
    )
    return item


def layer_root_ref(path: Path) -> str:
    return str(path.parent.parent)


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
    validate_source_id(source_id, path)
    validate_commit_hash(commit, path)
    if not namespace:
        raise ValidationError(f"Source namespace must be non-empty in {path}")
    return SourceDefinition(
        source_id=source_id,
        url=str(raw["url"]),
        commit=commit,
        namespace=namespace,
        trust_mode=str(raw["trust_mode"]),
        fingerprint=raw.get("fingerprint"),
        path=path,
        source_type=source_type,
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
            )
        )
    return bindings


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"Expected list, got {type(value).__name__}")
    return [str(item) for item in value]


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
            raise ValidationError(f"User override config may not declare baseline_policies in {config_path}")
        if config.repo_group_id or config.repo_class or config.normalized_remotes:
            raise ValidationError(f"User override config may not declare repo binding fields in {config_path}")
