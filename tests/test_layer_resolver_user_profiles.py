from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from team_agents.cli import main
from team_agents.loaders import load_corp_repo, load_user_layer
from team_agents.machine import load_machine_config
from team_agents.resolution import resolve_workspace


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def git(path: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(path),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


class LayerResolverUserProfilesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.corp = self.root / "corp"
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        git(self.workspace, "init")
        git(self.workspace, "config", "user.email", "test@example.com")
        git(self.workspace, "config", "user.name", "Test User")
        write(self.workspace / "README.md", "# workspace")
        git(self.workspace, "add", ".")
        git(self.workspace, "commit", "-m", "init")
        self.assertEqual(main(["init-corp-repo", "--dest", str(self.corp)]), 0)

    def tearDown(self) -> None:
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()

    def test_setup_user_profile_loads_from_corp_users_directory(self) -> None:
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
        machine = load_machine_config()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.workspace, machine, corp, user)
        self.assertIn("user.alice.skill.reviewer", result.enabled_skills)
        self.assertEqual(result.to_dict()["items"]["user.alice.skill.reviewer"]["activated_by"], ["user:alice"])

