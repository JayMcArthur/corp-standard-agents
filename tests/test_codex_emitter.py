from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from team_agents.cli import main


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


class CodexEmitterTests(unittest.TestCase):
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

    def test_setup_user_writes_codex_agents_with_managed_sections(self) -> None:
        body_path = self.corp / "users" / "alice" / "skills" / "reviewer" / "body.md"
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
        content = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        recursive_planning_source = self.home / ".team-agents" / "library" / "corp" / "skills" / "recursive-planning" / "body.md"
        expected_source = self.home / ".team-agents" / "library" / "user" / "skills" / "reviewer" / "body.md"
        expected = (
            "<!-- team-agents:start -->\n"
            "## Recursive Planning\n"
            f"Library body: `{recursive_planning_source}`\n\n"
            "## Recursive Planning\n\n"
            "        Use this as a realistic starter skill for broad, uncertain, multi-step work.\n\n"
            "## Reviewer\n"
            f"Library body: `{expected_source}`\n\n"
            "review body\n"
            "<!-- team-agents:end -->\n"
        )
        self.assertEqual(content, expected)

    def test_setup_user_merges_codex_managed_block_into_existing_file(self) -> None:
        write(
            self.corp / "users" / "alice" / "skills" / "reviewer" / "item.toml",
            """
            id = "user.alice.skill.reviewer"
            kind = "skill"
            title = "Reviewer"
            privacy = "repo-safe"
            target_tools = ["codex"]
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
        codex_path = self.home / ".codex" / "AGENTS.md"
        codex_path.parent.mkdir(parents=True, exist_ok=True)
        codex_path.write_text("manual intro\n<!-- team-agents:start -->\nold\n<!-- team-agents:end -->\n", encoding="utf-8")
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice", "--tool-target", "codex"]), 0)
        content = codex_path.read_text(encoding="utf-8")
        self.assertIn("manual intro", content)
        self.assertIn("## Reviewer", content)
