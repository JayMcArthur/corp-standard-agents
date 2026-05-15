from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from team_agents.cli import main


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


class ClaudeEmitterTests(unittest.TestCase):
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

    def test_setup_user_seeds_rendered_claude_skill_and_reseeds_after_body_change(self) -> None:
        body_path = self.corp / "users" / "alice" / "skills" / "reviewer" / "body.md"
        write(
            self.corp / "users" / "alice" / "skills" / "reviewer" / "item.toml",
            """
            id = "user.alice.skill.reviewer"
            kind = "skill"
            title = "Reviewer"
            privacy = "repo-safe"
            """,
        )
        write(body_path, "review body")
        write(
            self.corp / "users" / "alice" / "config.toml",
            """
            id = "alice"
            enabled_skills = ["user.alice.skill.reviewer"]
            preferred_agent_types = ["local-helper"]
            """,
        )
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        target = self.home / ".claude" / "skills" / "reviewer" / "SKILL.md"
        self.assertTrue(target.is_symlink())
        self.assertNotEqual(target.resolve(), body_path.resolve())
        content = target.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\nname: "))
        self.assertIn('description: "review body"', content)
        self.assertIn("review body", content)
        write(body_path, "updated review body")
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        self.assertIn("updated review body", target.read_text(encoding="utf-8"))

    def test_setup_user_preserves_claude_native_shape_when_body_already_has_frontmatter(self) -> None:
        write(
            self.corp / "users" / "alice" / "skills" / "reviewer" / "item.toml",
            """
            id = "user.alice.skill.reviewer"
            kind = "skill"
            title = "Reviewer"
            privacy = "repo-safe"
            """,
        )
        write(
            self.corp / "users" / "alice" / "skills" / "reviewer" / "body.md",
            """
            ---
            name: "Native Reviewer"
            description: "Native description"
            ---

            Native body
            """,
        )
        write(
            self.corp / "users" / "alice" / "config.toml",
            """
            id = "alice"
            enabled_skills = ["user.alice.skill.reviewer"]
            preferred_agent_types = ["local-helper"]
            """,
        )
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        content = (self.home / ".claude" / "skills" / "reviewer" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('name: "Native Reviewer"', content)
        self.assertIn('description: "Native description"', content)
        self.assertIn("Native body", content)

    def test_setup_user_prunes_stale_legacy_claude_skill_symlinks(self) -> None:
        legacy_skill = self.home / ".agents" / "skills" / "legacy-only" / "SKILL.md"
        write(legacy_skill, "# legacy")
        stale_target = self.home / ".claude" / "skills" / "legacy-only" / "SKILL.md"
        stale_target.parent.mkdir(parents=True, exist_ok=True)
        stale_target.symlink_to(legacy_skill)
        write(
            self.corp / "users" / "alice" / "skills" / "reviewer" / "item.toml",
            """
            id = "user.alice.skill.reviewer"
            kind = "skill"
            title = "Reviewer"
            privacy = "repo-safe"
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
        self.assertFalse((self.home / ".claude" / "skills" / "legacy-only").exists())
        self.assertTrue((self.home / ".claude" / "skills" / "reviewer" / "SKILL.md").exists())

    def test_setup_user_replaces_legacy_top_level_claude_skills_symlink(self) -> None:
        legacy_root = self.home / ".agents" / "skills"
        legacy_root.mkdir(parents=True, exist_ok=True)
        claude_root = self.home / ".claude" / "skills"
        claude_root.parent.mkdir(parents=True, exist_ok=True)
        claude_root.symlink_to(legacy_root, target_is_directory=True)
        write(
            self.corp / "users" / "alice" / "skills" / "reviewer" / "item.toml",
            """
            id = "user.alice.skill.reviewer"
            kind = "skill"
            title = "Reviewer"
            privacy = "repo-safe"
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
        self.assertFalse(claude_root.is_symlink())
        self.assertTrue((claude_root / "reviewer" / "SKILL.md").exists())
