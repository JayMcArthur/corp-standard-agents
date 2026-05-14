from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from team_agents.cli import main


class ScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)

    def tearDown(self) -> None:
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()

    def test_init_corp_repo_writes_root_docs_examples_and_users_readme(self) -> None:
        corp = self.root / "corp"
        self.assertEqual(main(["init-corp-repo", "--dest", str(corp)]), 0)
        self.assertTrue((corp / "README.md").exists())
        self.assertTrue((corp / "users" / "README.md").exists())
        self.assertTrue((corp / "org" / "skills" / "shell-global" / "item.toml").exists())
        self.assertTrue((corp / "org" / "policies" / "no-leaks" / "item.toml").exists())
        self.assertTrue((corp / "org" / "docs" / "authoring-example" / "item.toml").exists())

    def test_fresh_init_corp_repo_supports_setup_user_smoke(self) -> None:
        corp = self.root / "corp"
        self.assertEqual(main(["init-corp-repo", "--dest", str(corp)]), 0)
        self.assertEqual(main(["setup", "--corp-repo", str(corp), "--user", "demo"]), 0)
        self.assertTrue((corp / "users" / "demo" / "config.toml").exists())
