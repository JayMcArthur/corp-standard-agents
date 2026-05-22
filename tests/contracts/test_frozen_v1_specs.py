from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class FrozenV1SpecsTests(unittest.TestCase):
    def test_v1_spec_docs_exist(self) -> None:
        for name in [
            "item-schema.md",
            "activation-schema.md",
            "profile-job-schema.md",
            "materialization-config.md",
            "resolution-output.md",
            "agents-md-contract.md",
            "ci-governance-command-surface.md",
            "produced-artifact-manifest.md",
            "resolution-json.schema.json",
            "emitter-collision-rules.md",
            "canonical-id.md",
            "trust-and-pin-model.md",
        ]:
            with self.subTest(name=name):
                path = ROOT / "docs" / "specs" / "v1" / name
                self.assertTrue(path.exists(), path)
                self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 80)

    def test_public_v1_schemas_exist_and_parse(self) -> None:
        for name in [
            "item.schema.json",
            "activation.schema.json",
            "profile-job.schema.json",
            "materialization.schema.json",
            "resolution.schema.json",
        ]:
            with self.subTest(name=name):
                path = ROOT / "schemas" / name
                self.assertTrue(path.exists(), path)
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_public_resolution_schema_matches_runtime_contract(self) -> None:
        public_schema = json.loads((ROOT / "schemas" / "resolution.schema.json").read_text(encoding="utf-8"))
        docs_schema = json.loads((ROOT / "docs" / "specs" / "v1" / "resolution-json.schema.json").read_text(encoding="utf-8"))
        runtime_schema = json.loads(
            (ROOT / "src" / "team_agents" / "schemas" / "resolution-json-v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(public_schema, runtime_schema)
        self.assertEqual(docs_schema, runtime_schema)

    def test_public_item_schema_matches_runtime_contract(self) -> None:
        public_schema = json.loads((ROOT / "schemas" / "item.schema.json").read_text(encoding="utf-8"))
        runtime_schema = json.loads(
            (ROOT / "src" / "team_agents" / "schemas" / "item-toml-v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(public_schema, runtime_schema)

    def test_contract_suite_covers_frozen_surfaces(self) -> None:
        contract_tests = {path.name for path in (ROOT / "tests" / "contracts").glob("test_*.py")}
        for name in [
            "test_canonical_id_contract.py",
            "test_item_toml_contract.py",
            "test_resolution_json_contract.py",
            "test_tool_router_collisions_contract.py",
            "test_trust_model_contract.py",
        ]:
            self.assertIn(name, contract_tests)
