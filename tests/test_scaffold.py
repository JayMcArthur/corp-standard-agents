from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from team_agents.cli import main
from team_agents.loaders import load_corp_repo, load_user_layer
from team_agents.models import MachineConfig
from team_agents.resolution import resolve_workspace


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
        self.assertTrue((corp / "org" / "policies" / "no-leaks" / "item.toml").exists())
        self.assertTrue((corp / "org" / "docs" / "authoring-example" / "item.toml").exists())
        self.assertTrue((corp / "org" / "contracts" / "definition-of-done" / "item.toml").exists())
        self.assertTrue((corp / "org" / "flows" / "coder-loop" / "item.toml").exists())
        self.assertTrue((corp / "org" / "flows" / "pr-review" / "item.toml").exists())
        self.assertTrue((corp / "org" / "flows" / "prep-before-code" / "item.toml").exists())
        self.assertTrue((corp / "org" / "contracts" / "prep-artifacts" / "item.toml").exists())
        self.assertTrue((corp / "org" / "packs" / "corp-baseline" / "item.toml").exists())
        self.assertTrue((corp / "org" / "packs" / "preparation" / "item.toml").exists())
        self.assertTrue((corp / "org" / "profiles" / "coder.toml").exists())
        self.assertTrue((corp / "org" / "profiles" / "reviewer.toml").exists())
        self.assertTrue((corp / "repos" / "example-repo" / "contracts" / "repo-bootstrap" / "item.toml").exists())
        skill = (corp / "org" / "skills" / "recursive-planning" / "item.toml").read_text(encoding="utf-8")
        self.assertIn('owner = "agent-platform"', skill)
        self.assertIn('status = "active"', skill)
        self.assertIn('review_status = "approved"', skill)
        profile = (corp / "org" / "profiles" / "coder.toml").read_text(encoding="utf-8")
        self.assertIn('owner = "agent-platform"', profile)
        self.assertIn('status = "active"', profile)
        self.assertIn('autonomy_level = "interactive"', profile)
        self.assertIn("stop_conditions = [", profile)
        self.assertIn("allowed_tool_classes = [", profile)
        self.assertIn("forbidden_tool_classes = [", profile)
        contract = (corp / "org" / "contracts" / "definition-of-done" / "item.toml").read_text(encoding="utf-8")
        self.assertIn("evidence_required", contract)

    def test_fresh_init_corp_repo_supports_setup_user_smoke(self) -> None:
        corp = self.root / "corp"
        self.assertEqual(main(["init-corp-repo", "--dest", str(corp)]), 0)
        self.assertEqual(main(["setup", "--corp-repo", str(corp), "--user", "demo"]), 0)
        self.assertTrue((corp / "users" / "demo" / "config.toml").exists())

    def test_generated_corp_and_local_user_scaffolds_load_and_resolve(self) -> None:
        corp_root = self.root / "corp"
        user_root = self.root / "local-user"
        workspace = self.root / "workspace"
        workspace.mkdir()
        self.assertEqual(main(["init-corp-repo", "--dest", str(corp_root)]), 0)
        self.assertEqual(main(["init-user-layer", "--dest", str(user_root)]), 0)
        user_config = user_root / "config.toml"
        user_config.write_text(
            user_config.read_text(encoding="utf-8")
            + f"""

            [[workspace_binding]]
            name = "example"
            path = "{workspace.resolve()}"
            repo_id = "example-repo"
            """,
            encoding="utf-8",
        )
        user_readme = (user_root / "README.md").read_text(encoding="utf-8")
        self.assertIn("Local User Layer", user_readme)
        self.assertIn("team-agents attach --workspace", user_readme)
        self.assertIn("[[item_override]]", user_readme)
        machine = MachineConfig(
            corp_repo_path=corp_root,
            user_layer_path=user_root,
            cache_root=self.root / "cache",
            default_tool_target="all",
        )
        corp = load_corp_repo(corp_root)
        user = load_user_layer(user_root)
        result = resolve_workspace(workspace, machine, corp, user, profile="reviewer")
        self.assertIn("corp.example-org.policy.no-leaks", result.active_policies)
        self.assertIn("corp.example-org.contract.definition-of-done", result.active_contracts)
        self.assertIn("corp.example-org.contract.prep-artifacts", result.active_contracts)
        self.assertIn("corp.example-org.flow.prep-before-code", result.active_flows)
        self.assertIn("user.local.skill.personal-shell", result.enabled_skills)
