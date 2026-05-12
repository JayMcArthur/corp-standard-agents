from __future__ import annotations

from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.models import MachineConfig
from team_agents.toml_utils import read_toml, write_simple_toml


def machine_config_path() -> Path:
    return Path.home() / ".team-agents" / "config.toml"


def load_machine_config(path: Path | None = None) -> MachineConfig:
    config_path = path or machine_config_path()
    data = read_toml(config_path)
    required = ["corp_repo_path", "user_override_path", "cache_root", "default_tool_target"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValidationError(f"Machine config missing keys: {', '.join(missing)}")
    config = MachineConfig(
        corp_repo_path=Path(data["corp_repo_path"]).expanduser().resolve(),
        user_override_path=Path(data["user_override_path"]).expanduser().resolve(),
        cache_root=Path(data["cache_root"]).expanduser().resolve(),
        default_tool_target=str(data["default_tool_target"]),
    )
    if config.default_tool_target != "codex":
        raise ValidationError(f"Unsupported default_tool_target {config.default_tool_target!r}; expected 'codex'")
    return config


def write_machine_config(config: MachineConfig, path: Path | None = None) -> Path:
    config_path = path or machine_config_path()
    write_simple_toml(
        config_path,
        {
            "corp_repo_path": str(config.corp_repo_path),
            "user_override_path": str(config.user_override_path),
            "cache_root": str(config.cache_root),
            "default_tool_target": config.default_tool_target,
        },
    )
    return config_path


def ensure_user_override_layout(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in ["skills", "policies", "docs", "sources", "workspaces"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    config_path = root / "config.toml"
    if not config_path.exists():
        write_simple_toml(
            config_path,
            {
                "id": "user-local",
                "enabled_sources": [],
                "disabled_sources": [],
                "enabled_skills": [],
                "disabled_skills": [],
                "optional_policies": [],
                "disabled_optional_policies": [],
                "docs": [],
                "disabled_docs": [],
                "preferred_agent_types": [],
            },
        )
