from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.item_schema import ITEM_TOML_V1_SCHEMA_PATH, load_item_toml_schema, validate_item_toml


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "contracts" / "fixtures" / "item_toml"


def read_fixture(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


class ItemTomlContractTests(unittest.TestCase):
    def test_schema_file_exists_and_declares_required_fields(self) -> None:
        self.assertTrue(ITEM_TOML_V1_SCHEMA_PATH.exists())
        schema = load_item_toml_schema()
        self.assertEqual(schema["required"], ["id", "kind", "title", "privacy"])
        self.assertEqual(
            schema["properties"]["kind"]["enum"],
            ["skill", "policy", "doc", "contract", "flow", "pack", "profile"],
        )

    def test_existing_item_toml_fixtures_validate(self) -> None:
        item_paths = sorted((ROOT / "examples").rglob("item.toml")) + sorted((ROOT / ".agents").rglob("item.toml"))
        self.assertTrue(item_paths)
        for path in item_paths:
            with self.subTest(path=str(path)):
                validate_item_toml(read_fixture(path), path)

    def test_positive_fixture_with_optional_metadata_validates(self) -> None:
        path = FIXTURES / "valid" / "full-metadata.toml"
        validate_item_toml(read_fixture(path), path)

    def test_missing_required_field_is_rejected(self) -> None:
        path = FIXTURES / "invalid" / "missing-title.toml"
        with self.assertRaisesRegex(ValidationError, r"\$\.title is required"):
            validate_item_toml(read_fixture(path), path)

    def test_unknown_kind_is_rejected(self) -> None:
        path = FIXTURES / "invalid" / "unknown-kind.toml"
        with self.assertRaisesRegex(ValidationError, r"\$\.kind must be one of"):
            validate_item_toml(read_fixture(path), path)

    def test_unknown_field_is_rejected(self) -> None:
        path = FIXTURES / "invalid" / "unknown-field.toml"
        with self.assertRaisesRegex(ValidationError, r"unsupported properties: made_up"):
            validate_item_toml(read_fixture(path), path)

    def test_canonical_id_kind_mismatch_is_rejected(self) -> None:
        path = FIXTURES / "invalid" / "kind-mismatch.toml"
        with self.assertRaisesRegex(ValidationError, r"Canonical id kind mismatch"):
            validate_item_toml(read_fixture(path), path)
