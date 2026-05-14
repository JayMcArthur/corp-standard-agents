from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class InstallScriptTests(unittest.TestCase):
    def test_install_script_is_idempotent_and_writes_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            env = dict(os.environ)
            env["HOME"] = str(home)
            subprocess.run(["bash", "scripts/install.sh"], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            subprocess.run(["bash", "scripts/install.sh"], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            wrapper = home / ".local" / "bin" / "team-agents"
            self.assertTrue(wrapper.exists())
            help_run = subprocess.run([str(wrapper), "--help"], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            self.assertIn("team-agents", help_run.stdout)

    def test_uninstall_script_removes_wrapper_and_venv_but_keeps_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            env = dict(os.environ)
            env["HOME"] = str(home)
            subprocess.run(["bash", "scripts/install.sh"], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            state_root = home / ".team-agents"
            (state_root / "config.toml").write_text("corp_repo_path = \"/tmp/corp\"\n", encoding="utf-8")
            subprocess.run(["bash", "scripts/uninstall.sh"], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            self.assertFalse((home / ".local" / "bin" / "team-agents").exists())
            self.assertFalse((state_root / "venv").exists())
            self.assertTrue(state_root.exists())
            self.assertTrue((state_root / "config.toml").exists())
