from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from team_agents.schema_validation import validate_schema_instance


RESOLUTION_JSON_V1_SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "resolution-json-v1.schema.json"


def load_resolution_json_schema() -> dict[str, Any]:
    return json.loads(RESOLUTION_JSON_V1_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_resolution_json(payload: dict[str, Any]) -> None:
    schema = load_resolution_json_schema()
    validate_schema_instance(payload, schema, "$", schema)
