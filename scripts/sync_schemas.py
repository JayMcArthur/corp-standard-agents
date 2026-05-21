#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

COPIES = {
    "src/team_agents/schemas/item-toml-v1.schema.json": [
        "schemas/item.schema.json",
    ],
    "src/team_agents/schemas/resolution-json-v1.schema.json": [
        "schemas/resolution.schema.json",
        "docs/specs/v1/resolution-json.schema.json",
    ],
}


def main() -> int:
    for source, targets in COPIES.items():
        source_path = ROOT / source
        for target in targets:
            target_path = ROOT / target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target_path)
            print(f"{source} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
