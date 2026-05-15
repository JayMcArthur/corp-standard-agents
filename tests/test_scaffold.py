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
        self.assertTrue((corp / "org" / "skills" / "recursive-planning" / "item.toml").exists())
        self.assertTrue((corp / "org" / "skills" / "repo-onboarding" / "item.toml").exists())
        self.assertTrue((corp / "org" / "policies" / "no-leaks" / "item.toml").exists())
        self.assertTrue((corp / "org" / "docs" / "authoring-example" / "item.toml").exists())
        self.assertTrue((corp / "repo-groups" / "platform" / "config.toml").exists())
        self.assertTrue((corp / "repos" / "internal-app" / "config.toml").exists())

    def test_init_corp_repo_starter_model_links_group_and_unknown_onboarding(self) -> None:
        corp = self.root / "corp"
        self.assertEqual(main(["init-corp-repo", "--dest", str(corp)]), 0)
        org_config = (corp / "org" / "config.toml").read_text(encoding="utf-8")
        repo_group_config = (corp / "repo-groups" / "platform" / "config.toml").read_text(encoding="utf-8")
        repo_config = (corp / "repos" / "internal-app" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('minimal_enabled_skills = ["corp.example-org.skill.repo-onboarding"]', org_config)
        self.assertIn('enabled_skills = ["corp.example-org.skill.recursive-planning"]', repo_group_config)
        self.assertIn('repo_group_id = "platform"', repo_config)

    def test_fresh_init_corp_repo_supports_setup_user_smoke(self) -> None:
        corp = self.root / "corp"
        self.assertEqual(main(["init-corp-repo", "--dest", str(corp)]), 0)
        self.assertEqual(main(["setup", "--corp-repo", str(corp), "--user", "demo"]), 0)
        self.assertTrue((corp / "users" / "demo" / "config.toml").exists())
        self.assertTrue((corp / "users" / "demo" / "skills" / "personal-shell" / "item.toml").exists())
        self.assertTrue((self.home / ".claude" / "skills" / "personal-shell" / "SKILL.md").exists())

    def test_init_user_profile_starts_with_personal_shell_only(self) -> None:
        corp = self.root / "corp"
        self.assertEqual(main(["init-corp-repo", "--dest", str(corp)]), 0)
        self.assertEqual(main(["setup", "--corp-repo", str(corp), "--user", "demo"]), 0)
        config = (corp / "users" / "demo" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('enabled_skills = ["user.demo.skill.personal-shell"]', config)
        self.assertIn('preferred_agent_types = ["local-helper"]', config)
