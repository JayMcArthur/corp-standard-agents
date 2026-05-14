from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from team_agents.cli import main


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


class NativeSourceEmitterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.corp = self.root / "corp"
        self.source = self.root / "source"
        self.assertEqual(main(["init-corp-repo", "--dest", str(self.corp)]), 0)

    def tearDown(self) -> None:
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()

    def test_claude_native_external_source_appears_in_all_global_emitters(self) -> None:
        self.source.mkdir()
        git(self.source, "init")
        git(self.source, "config", "user.email", "test@example.com")
        git(self.source, "config", "user.name", "Test User")
        write(
            self.source / "reviewer" / "SKILL.md",
            "---\n"
            'name: "External Reviewer"\n'
            'description: "External source review helper"\n'
            'tools: ["claude", "codex", "cursor"]\n'
            "---\n\n"
            "External body\n",
        )
        git(self.source, "add", ".")
        git(self.source, "commit", "-m", "source")
        commit = git(self.source, "rev-parse", "HEAD")
        write(
            self.corp / "users" / "alice" / "sources" / "ext.toml",
            f"""
            id = "ext"
            url = "{self.source}"
            commit = "{commit}"
            namespace = "shared"
            trust_mode = "trust-on-first-use"
            """,
        )
        write(
            self.corp / "users" / "alice" / "config.toml",
            """
            id = "alice"
            enabled_sources = ["ext"]
            enabled_skills = ["user.shared.skill.reviewer"]
            preferred_agent_types = ["local-helper"]
            """,
        )
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        self.assertTrue((self.home / ".claude" / "skills" / "reviewer" / "SKILL.md").exists())
        self.assertTrue((self.home / ".cursor" / "rules" / "reviewer.mdc").exists())
        codex_content = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("External Reviewer", codex_content)
        self.assertIn(".team-agents/library/external/ext@", codex_content)
