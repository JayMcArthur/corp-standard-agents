from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from team_agents.cli import main
from team_agents.library import library_root
from team_agents.machine import load_machine_config


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


class LibraryManagerTests(unittest.TestCase):
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

    def test_setup_user_creates_library_symlinks_and_is_idempotent(self) -> None:
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
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        config = load_machine_config()
        root = library_root(config)
        self.assertTrue((root / "corp").is_symlink())
        self.assertTrue((root / "user").is_symlink())
        self.assertEqual((root / "corp").resolve(), self.corp.resolve())
        self.assertEqual((root / "user").resolve(), (self.corp / "users" / "alice").resolve())

