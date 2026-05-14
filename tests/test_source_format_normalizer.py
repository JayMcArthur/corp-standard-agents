from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.library import render_codex_section, render_cursor_rule
from team_agents.loaders import load_item, load_items
from team_agents.output import render_skill_markdown


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


class SourceFormatNormalizerTests(unittest.TestCase):
    def test_item_toml_and_body_md_round_trip_to_internal_item_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "reviewer"
            write(
                skill_dir / "item.toml",
                """
                id = "user.alice.skill.reviewer"
                kind = "skill"
                title = "Reviewer"
                privacy = "repo-safe"
                recommended_agent_types = ["shell"]
                """,
            )
            write(skill_dir / "body.md", "review body")
            item = load_item(skill_dir, "skill", source_type="user", source_namespace="alice")
            self.assertEqual(item.item_id, "user.alice.skill.reviewer")
            self.assertEqual(item.slug, "reviewer")
            self.assertEqual(item.body, "review body\n")
            self.assertEqual(item.recommended_agent_types, ["shell"])

    def test_claude_native_skill_fixture_normalizes_to_internal_item(self) -> None:
        fixture_root = Path(__file__).resolve().parent.parent / "examples" / "external-source" / "claude-native"
        items = load_items(fixture_root, source_type="external", source_namespace="shared", allow_native_source_formats=True)
        item = items["external.shared.skill.reviewer"]
        self.assertEqual(item.title, "Claude Reviewer")
        self.assertEqual(item.claude_model, "opus")
        self.assertEqual(item.target_tools, ["claude", "codex", "cursor"])
        self.assertTrue(item.body.startswith("---\nname:"))
        self.assertIn('name: "Claude Reviewer"', render_skill_markdown(item))
        self.assertIn("Library body:", render_codex_section(Path("/tmp/library"), item))
        self.assertIn('description: "Review code carefully."', render_cursor_rule(item))

    def test_cursor_native_rule_fixture_normalizes_to_internal_item(self) -> None:
        fixture_root = Path(__file__).resolve().parent.parent / "examples" / "external-source" / "cursor-native"
        items = load_items(fixture_root, source_type="external", source_namespace="shared", allow_native_source_formats=True)
        item = items["external.shared.skill.reviewer"]
        self.assertEqual(item.cursor_globs, ["src/**/*.py", "tests/**/*.py"])
        self.assertEqual(item.cursor_always_apply, True)
        self.assertEqual(item.target_tools, ["cursor"])
        self.assertIn("Cursor Reviewer", item.body)
        self.assertIn('description: "Review changed application code"', render_cursor_rule(item))
        self.assertNotIn("globs", render_skill_markdown(item))
        self.assertIn("Cursor Reviewer", render_codex_section(Path("/tmp/library"), item))

    def test_claude_native_missing_name_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "reviewer" / "SKILL.md",
                "---\n"
                'description: "Missing name"\n'
                "---\n\n"
                "Broken\n",
            )
            with self.assertRaisesRegex(ValidationError, "missing required frontmatter field 'name'"):
                load_items(root, source_type="external", source_namespace="shared", allow_native_source_formats=True)

    def test_cursor_native_malformed_frontmatter_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / ".cursor" / "rules" / "reviewer.mdc",
                "---\n"
                'description "broken"\n'
                "---\n\n"
                "Broken\n",
            )
            with self.assertRaisesRegex(ValidationError, "Malformed frontmatter line"):
                load_items(root, source_type="external", source_namespace="shared", allow_native_source_formats=True)
