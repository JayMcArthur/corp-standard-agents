from __future__ import annotations

from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.layer_configs import load_layer_config, load_profile_configs, parse_workspace_bindings
from team_agents.models import CorpRepo, LayerData, UserLayer
from team_agents.source_manifests import load_personal_sources, load_source_registry, validate_repo_indexes
from team_agents.standard_items import load_item, load_items
from team_agents.toml_utils import read_toml


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
    config = load_layer_config(path, layer_name)
    items = load_items(path, source_type=source_type, source_namespace=config.identifier)
    profiles = load_profile_configs(path)
    return LayerData(config=config, items=items, profiles=profiles)
