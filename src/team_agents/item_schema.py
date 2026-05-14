from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from team_agents.errors import ValidationError
from team_agents.schema_validation import validate_schema_instance
from team_agents.validation import validate_canonical_id


ITEM_TOML_V1_SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "item-toml-v1.schema.json"


def load_item_toml_schema() -> dict[str, Any]:
    return json.loads(ITEM_TOML_V1_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_item_toml(raw: dict[str, Any], path: Path) -> None:
    schema = load_item_toml_schema()
    validate_schema_instance(raw, schema, "$", schema)
    validate_canonical_id(str(raw["id"]), expected_kind=str(raw["kind"]), path=path)
