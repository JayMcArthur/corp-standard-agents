from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from team_agents.errors import ValidationError


def read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"Missing TOML file: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValidationError(f"Invalid TOML in {path}: {exc}") from exc


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        inner = ", ".join(_toml_value(item) for item in value)
        return f"[{inner}]"
    if value is None:
        raise ValueError("Cannot serialize None into TOML")
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_simple_toml(path: Path, values: dict[str, Any]) -> None:
    lines = []
    for key, value in values.items():
        lines.append(f"{key} = {_toml_value(value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_toml_document(path: Path, values: dict[str, Any]) -> None:
    lines: list[str] = []
    table_lines: list[str] = []
    for key, value in values.items():
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            for item in value:
                table_lines.append(f"[[{key}]]")
                for item_key, item_value in item.items():
                    table_lines.append(f"{item_key} = {_toml_value(item_value)}")
                table_lines.append("")
            continue
        if isinstance(value, dict):
            raise ValueError(f"Nested TOML tables are not supported for key {key}")
        lines.append(f"{key} = {_toml_value(value)}")
    if table_lines:
        if lines:
            lines.append("")
        lines.extend(table_lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
