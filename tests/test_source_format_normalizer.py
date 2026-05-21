from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from team_agents.errors import ValidationError
from team_agents.emitters.claude import render_skill_markdown
from team_agents.frontmatter import parse_frontmatter_document
from team_agents.library import render_codex_section, render_cursor_rule
from team_agents.loaders import load_item, load_items


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

    def test_claude_native_multiline_list_frontmatter_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "reviewer" / "SKILL.md",
                "---\n"
                'name: "Reviewer"\n'
                'description: "Review things"\n'
                "tools:\n"
                "  - Bash(npx reviewer *)\n"
                "  - Read\n"
                "---\n\n"
                "Body\n",
            )
            items = load_items(root, source_type="external", source_namespace="shared", allow_native_source_formats=True)
            item = items["external.shared.skill.reviewer"]
            self.assertEqual(item.target_tools, ["Bash(npx reviewer *)", "Read"])

    def test_claude_native_folded_text_frontmatter_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "reviewer" / "SKILL.md",
                "---\n"
                'name: "Reviewer"\n'
                "description: >\n"
                "  First line\n"
                "  second line\n"
                "---\n\n"
                "Body\n",
            )
            metadata, _ = parse_frontmatter_document((root / "reviewer" / "SKILL.md").read_text(encoding="utf-8"), root / "reviewer" / "SKILL.md")
            self.assertEqual(metadata["description"], "First line second line")
            items = load_items(root, source_type="external", source_namespace="shared", allow_native_source_formats=True)
            item = items["external.shared.skill.reviewer"]
            self.assertEqual(item.title, "Reviewer")

    def test_claude_native_skills_folder_layout_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "skills" / "taste-skill" / "SKILL.md",
                "---\n"
                'name: "Taste Skill"\n'
                'description: "Design taste guidance"\n'
                "---\n\n"
                "Taste body\n",
            )
            items = load_items(root, source_type="external", source_namespace="taste", allow_native_source_formats=True)
            item = items["external.taste.skill.taste-skill"]
            self.assertEqual(item.title, "Taste Skill")
            self.assertEqual(item.slug, "taste-skill")

    def test_hidden_claude_skills_layout_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / ".claude" / "skills" / "ui-ux-pro-max" / "SKILL.md",
                "---\n"
                'name: "UI UX Pro Max"\n'
                'description: "Design intelligence"\n'
                "metadata:\n"
                '  author: "claudekit"\n'
                '  version: "1.0.0"\n'
                "---\n\n"
                "Design body\n",
            )
            items = load_items(root, source_type="external", source_namespace="uiux", allow_native_source_formats=True)
            item = items["external.uiux.skill.ui-ux-pro-max"]
            self.assertEqual(item.title, "UI UX Pro Max")
            self.assertEqual(item.slug, "ui-ux-pro-max")

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
