from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.loaders import load_items
from team_agents.validation import validate_canonical_id


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


class CanonicalIdContractTests(unittest.TestCase):
    def test_valid_ids_parse(self) -> None:
        for item_id in [
            "corp.shadowknight.skill.shell-global",
            "external.shared.policy.ext-policy",
            "user.local.doc.personal_notes",
        ]:
            with self.subTest(item_id=item_id):
                parts = validate_canonical_id(item_id)
                self.assertEqual(".".join(parts), item_id)

    def test_invalid_ids_are_rejected(self) -> None:
        for item_id in [
            "team.shadowknight.skill.shell-global",
            "Corp.shadowknight.skill.shell-global",
            "corp.shadowknight.widget.shell-global",
            "corp.shadowknight.skill",
            "corp.shadowknight.skill.bad.slug",
            "corp.shadowknight.skill.-bad",
        ]:
            with self.subTest(item_id=item_id):
                with self.assertRaisesRegex(ValidationError, "Invalid canonical id"):
                    validate_canonical_id(item_id)

    def test_kind_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "Canonical id kind mismatch"):
            validate_canonical_id("corp.shadowknight.policy.no-leaks", expected_kind="skill")

    def test_duplicate_ids_in_same_layer_fail_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "skills" / "first" / "item.toml",
                """
                id = "corp.shadowknight.skill.same-id"
                kind = "skill"
                title = "First"
                privacy = "repo-safe"
                """,
            )
            write(root / "skills" / "first" / "body.md", "first")
            write(
                root / "skills" / "second" / "item.toml",
                """
                id = "corp.shadowknight.skill.same-id"
                kind = "skill"
                title = "Second"
                privacy = "repo-safe"
                """,
            )
            write(root / "skills" / "second" / "body.md", "second")
            with self.assertRaisesRegex(ValidationError, "Duplicate canonical id in layer"):
                load_items(root, source_type="corp", source_namespace="shadowknight")
