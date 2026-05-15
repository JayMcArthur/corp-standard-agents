from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from team_agents.cli import main


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


class CursorEmitterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.corp = self.root / "corp"
        self.assertEqual(main(["init-corp-repo", "--dest", str(self.corp)]), 0)

    def tearDown(self) -> None:
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()

    def test_setup_user_writes_cursor_rule_symlink_with_frontmatter(self) -> None:
        write(
            self.corp / "users" / "alice" / "skills" / "reviewer" / "item.toml",
            """
            id = "user.alice.skill.reviewer"
            kind = "skill"
            title = "Reviewer"
            privacy = "repo-safe"
            target_tools = ["claude", "codex", "cursor"]
            cursor_globs = ["src/**/*.py"]
            cursor_always_apply = true
            """,
        )
        write(self.corp / "users" / "alice" / "skills" / "reviewer" / "body.md", "review body")
        write(
            self.corp / "users" / "alice" / "config.toml",
            """
            id = "alice"
            enabled_skills = ["user.alice.skill.reviewer"]
            preferred_agent_types = ["local-helper"]
            """,
        )
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        rule_path = self.home / ".cursor" / "rules" / "reviewer.mdc"
        self.assertTrue(rule_path.is_symlink())
        content = rule_path.read_text(encoding="utf-8")
        expected = (
            "---\n"
            'description: "review body"\n'
            'globs: ["src/**/*.py"]\n'
            "alwaysApply: true\n"
            "---\n\n"
            "review body\n"
        )
        self.assertEqual(content, expected)

    def test_setup_user_with_all_targets_seeds_claude_codex_and_cursor(self) -> None:
        write(
            self.corp / "users" / "alice" / "skills" / "reviewer" / "item.toml",
            """
            id = "user.alice.skill.reviewer"
            kind = "skill"
            title = "Reviewer"
            privacy = "repo-safe"
            target_tools = ["claude", "codex", "cursor"]
            """,
        )
        write(self.corp / "users" / "alice" / "skills" / "reviewer" / "body.md", "review body")
        write(
            self.corp / "users" / "alice" / "config.toml",
            """
            id = "alice"
            enabled_skills = ["user.alice.skill.reviewer"]
            preferred_agent_types = ["local-helper"]
            """,
        )
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        self.assertTrue((self.home / ".claude" / "skills" / "reviewer" / "SKILL.md").exists())
        self.assertTrue((self.home / ".codex" / "AGENTS.md").exists())
        self.assertTrue((self.home / ".cursor" / "rules" / "reviewer.mdc").exists())

    def test_setup_user_prunes_stale_managed_cursor_rules(self) -> None:
        rendered_root = self.home / ".team-agents" / "library" / "rendered" / "cursor" / "rules"
        rendered_root.mkdir(parents=True, exist_ok=True)
        legacy_rule = rendered_root / "legacy-only.mdc"
        write(legacy_rule, "---\ndescription: legacy\n---\nlegacy\n")
        stale_target = self.home / ".cursor" / "rules" / "legacy-only.mdc"
        stale_target.parent.mkdir(parents=True, exist_ok=True)
        stale_target.symlink_to(legacy_rule)
        write(
            self.corp / "users" / "alice" / "skills" / "reviewer" / "item.toml",
            """
            id = "user.alice.skill.reviewer"
            kind = "skill"
            title = "Reviewer"
            privacy = "repo-safe"
            target_tools = ["cursor"]
            """,
        )
        write(self.corp / "users" / "alice" / "skills" / "reviewer" / "body.md", "review body")
        write(
            self.corp / "users" / "alice" / "config.toml",
            """
            id = "alice"
            enabled_skills = ["user.alice.skill.reviewer"]
            preferred_agent_types = ["local-helper"]
            """,
        )
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        self.assertFalse(stale_target.exists())
        self.assertTrue((self.home / ".cursor" / "rules" / "reviewer.mdc").exists())
