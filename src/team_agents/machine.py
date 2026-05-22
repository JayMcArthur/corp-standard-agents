from __future__ import annotations

import os
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.materialization import validate_materialization_strategy
from team_agents.models import MachineConfig
from team_agents.toml_utils import read_toml, write_toml_document


def machine_config_path() -> Path:
    override = os.environ.get("TEAM_AGENTS_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".team-agents" / "config.toml"


def load_machine_config(path: Path | None = None) -> MachineConfig:
    config_path = path or machine_config_path()
    data = read_toml(config_path)
    required = ["corp_repo_path", "user_layer_path", "cache_root", "default_tool_target"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValidationError(f"Machine config missing keys: {', '.join(missing)}")
    materialization = data.get("materialization", {})
    if materialization is None:
        materialization = {}
    if not isinstance(materialization, dict):
        raise ValidationError("Machine config [materialization] must be a table")
    strategy = str(materialization.get("strategy", data.get("materialization_strategy", "auto")))
    validate_materialization_strategy(strategy)
    config = MachineConfig(
        corp_repo_path=Path(data["corp_repo_path"]).expanduser().resolve(),
        user_layer_path=Path(data["user_layer_path"]).expanduser().resolve(),
        cache_root=Path(data["cache_root"]).expanduser().resolve(),
        default_tool_target=str(data["default_tool_target"]),
        user_name=str(data["user_name"]) if data.get("user_name") is not None else None,
        materialization_strategy=strategy,
    )
    if config.default_tool_target not in {"all", "codex", "claude", "cursor"}:
        raise ValidationError(
            f"Unsupported default_tool_target {config.default_tool_target!r}; expected one of 'all', 'codex', 'claude', 'cursor'"
        )
    return config


def write_machine_config(config: MachineConfig, path: Path | None = None) -> Path:
    config_path = path or machine_config_path()
    payload = {
        "corp_repo_path": str(config.corp_repo_path),
        "user_layer_path": str(config.user_layer_path),
        "cache_root": str(config.cache_root),
        "default_tool_target": config.default_tool_target,
        "materialization": {"strategy": config.materialization_strategy},
    }
    if config.user_name is not None:
        payload["user_name"] = config.user_name
    write_toml_document(config_path, payload)
    return config_path


def ensure_user_layer_layout(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in ["skills", "policies", "contexts", "completion_gates", "playbooks", "packs", "profiles", "activations", "sources", "workspaces"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    config_path = root / "config.toml"
    if not config_path.exists():
        write_toml_document(
            config_path,
            {
                "id": "user-local",
                "enabled_sources": [],
                "disabled_sources": [],
                "enabled_skills": [],
                "disabled_skills": [],
                "optional_policies": [],
                "disabled_optional_policies": [],
                "contexts": [],
                "disabled_contexts": [],
                "preferred_agent_types": [],
            },
        )
