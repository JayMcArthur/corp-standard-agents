from __future__ import annotations

import os
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO

from team_agents.cli import main
from team_agents.library import library_root
from team_agents.machine import load_machine_config, write_machine_config
from team_agents.models import MachineConfig


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

    def write_user_skill(self) -> None:
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

    def test_setup_copy_materialization_is_idempotent(self) -> None:
        self.write_user_skill()
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        self.assertEqual(main(["setup", "--corp-repo", str(self.corp), "--user", "alice"]), 0)
        config = load_machine_config()
        root = library_root(config)
        self.assertEqual(config.materialization_strategy, "auto")
        self.assertFalse((root / "corp").is_symlink())
        self.assertFalse((root / "user").is_symlink())
        self.assertTrue((root / "corp" / "org" / "config.toml").exists())
        self.assertTrue((root / "user" / "skills" / "reviewer" / "body.md").exists())

    def test_setup_symlink_materialization_remains_available(self) -> None:
        self.write_user_skill()
        self.assertEqual(
            main(
                [
                    "setup",
                    "--corp-repo",
                    str(self.corp),
                    "--user",
                    "alice",
                    "--materialization-strategy",
                    "symlink",
                ]
            ),
            0,
        )
        config = load_machine_config()
        root = library_root(config)
        self.assertEqual(config.materialization_strategy, "symlink")
        self.assertTrue((root / "corp").is_symlink())
        self.assertTrue((root / "user").is_symlink())
        self.assertEqual((root / "corp").resolve(), self.corp.resolve())
        self.assertEqual((root / "user").resolve(), (self.corp / "users" / "alice").resolve())

    def test_render_only_materialization_omits_source_links(self) -> None:
        self.write_user_skill()
        self.assertEqual(
            main(
                [
                    "setup",
                    "--corp-repo",
                    str(self.corp),
                    "--user",
                    "alice",
                    "--materialization-strategy",
                    "render-only",
                ]
            ),
            0,
        )
        config = load_machine_config()
        root = library_root(config)
        self.assertEqual(config.materialization_strategy, "render-only")
        self.assertFalse((root / "corp").exists())
        self.assertFalse((root / "user").exists())
        self.assertTrue((root / "rendered" / "claude" / "skills" / "reviewer" / "SKILL.md").exists())
        codex_content = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("review body", codex_content)
        self.assertNotIn("Library body:", codex_content)

    def test_doctor_reports_materialization_strategy(self) -> None:
        self.write_user_skill()
        self.assertEqual(
            main(
                [
                    "setup",
                    "--corp-repo",
                    str(self.corp),
                    "--user",
                    "alice",
                    "--materialization-strategy",
                    "copy",
                ]
            ),
            0,
        )
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["doctor", "--workspace", str(self.root), "--json"]), 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report["machine_config"]["materialization_strategy"], "copy")
        self.assertEqual(report["machine_config"]["effective_materialization_strategy"], "copy")
        checks = {check["name"]: check for check in report["checks"]}
        self.assertEqual(checks["materialization-strategy"]["status"], "ok")

    def test_doctor_reports_platform_unsupported_materialization_mode(self) -> None:
        if os.name == "nt":
            self.skipTest("junction is supported on Windows")
        self.write_user_skill()
        write_machine_config(
            MachineConfig(
                corp_repo_path=self.corp,
                user_layer_path=self.corp / "users" / "alice",
                cache_root=self.root / "cache",
                default_tool_target="all",
                user_name="alice",
                materialization_strategy="junction",
            )
        )
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["doctor", "--workspace", str(self.root), "--json"]), 0)
        report = json.loads(out.getvalue())
        checks = {check["name"]: check for check in report["checks"]}
        self.assertEqual(checks["materialization-strategy"]["status"], "warn")
        self.assertIn("only supported on Windows", checks["materialization-support"]["detail"])
