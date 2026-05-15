from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
import hashlib
from unittest.mock import patch

from team_agents.cli import build_parser, main
from team_agents.errors import ProtectionError, ResolutionError, ValidationError
from team_agents.loaders import load_corp_repo, load_user_overrides
from team_agents.machine import load_machine_config
from team_agents.models import MachineConfig
from team_agents.output import write_sync_output
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


def init_repo(path: Path, remote: str, tracked_agents: str | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test User")
    write(path / "README.md", f"# {path.name}")
    if tracked_agents is not None:
        write(path / "AGENTS.md", tracked_agents)
    git(path, "add", ".")
    git(path, "commit", "-m", "init")
    git(path, "remote", "add", "origin", remote)


def create_external_source_repo(root: Path) -> tuple[str, str]:
    repo = root / "external-source"
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    write(
        repo / "skills" / "ext-review" / "item.toml",
        """
        id = "external.shared.skill.ext-review"
        kind = "skill"
        title = "External Review"
        privacy = "repo-safe"
        timeout_seconds = 30
        """,
    )
    write(repo / "skills" / "ext-review" / "body.md", "External review body")
    write(
        repo / "skills" / "ext-lint" / "item.toml",
        """
        id = "external.shared.skill.ext-lint"
        kind = "skill"
        title = "External Lint"
        privacy = "repo-safe"
        timeout_seconds = 15
        """,
    )
    write(repo / "skills" / "ext-lint" / "body.md", "External lint body")
    write(
        repo / "policies" / "ext-policy" / "item.toml",
        """
        id = "external.shared.policy.ext-policy"
        kind = "policy"
        title = "External Policy"
        privacy = "repo-safe"
        """,
    )
    write(repo / "policies" / "ext-policy" / "body.md", "External policy body")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "external source")
    return str(repo), git(repo, "rev-parse", "HEAD")


def create_personal_source_repo(root: Path) -> tuple[str, str]:
    repo = root / "personal-source"
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    write(
        repo / "skills" / "personal-remote" / "item.toml",
        """
        id = "user.remote.skill.personal-remote"
        kind = "skill"
        title = "Personal Remote"
        privacy = "repo-safe"
        """,
    )
    write(repo / "skills" / "personal-remote" / "body.md", "Personal remote body")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "personal source")
    return str(repo), git(repo, "rev-parse", "HEAD")


def create_collision_source_repo(root: Path) -> tuple[str, str]:
    repo = root / "collision-source"
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    write(
        repo / "skills" / "ext-review" / "item.toml",
        """
        id = "external.collision.skill.ext-review"
        kind = "skill"
        title = "Collision Review"
        privacy = "repo-safe"
        """,
    )
    write(repo / "skills" / "ext-review" / "body.md", "Collision review body")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "collision source")
    return str(repo), git(repo, "rev-parse", "HEAD")


def create_targeted_collision_source_repo(root: Path, name: str, item_id: str, target_tool: str) -> tuple[str, str]:
    repo = root / name
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    write(
        repo / "skills" / "shared-helper" / "item.toml",
        f"""
        id = "{item_id}"
        kind = "skill"
        title = "Shared Helper"
        privacy = "repo-safe"
        target_tools = ["{target_tool}"]
        """,
    )
    write(repo / "skills" / "shared-helper" / "body.md", f"{target_tool} helper body")
    git(repo, "add", ".")
    git(repo, "commit", "-m", f"{name} source")
    return str(repo), git(repo, "rev-parse", "HEAD")


def create_corp_repo(
    root: Path,
    external_url: str,
    external_commit: str,
    internal_remote: str,
    internal_alt_remote: str,
    client_private_remote: str,
    client_tracked_remote: str,
) -> Path:
    corp = root / "corp-control"
    write(
        corp / "org" / "config.toml",
        """
        id = "shadowknight"
        enabled_sources = ["shared-ext"]
        enabled_skills = ["corp.shadowknight.skill.shell-global"]
        baseline_policies = ["corp.shadowknight.policy.no-leaks"]
        recommended_agent_types = ["shell"]
        minimal_enabled_skills = ["corp.shadowknight.skill.shell-global"]
        protected_fields = ["baseline_policies", "privacy_rules"]
        """,
    )
    write(
        corp / "org" / "skills" / "shell-global" / "item.toml",
        """
        id = "corp.shadowknight.skill.shell-global"
        kind = "skill"
        title = "Shell Global"
        privacy = "repo-safe"
        """,
    )
    write(corp / "org" / "skills" / "shell-global" / "body.md", "Shell global body")
    write(
        corp / "org" / "skills" / "repo-onboarding" / "item.toml",
        """
        id = "corp.shadowknight.skill.repo-onboarding"
        kind = "skill"
        title = "Repo Onboarding"
        privacy = "repo-safe"
        usage_mode = "one-time"
        """,
    )
    write(corp / "org" / "skills" / "repo-onboarding" / "body.md", "Repo onboarding body")
    write(
        corp / "org" / "skills" / "internal-ops" / "item.toml",
        """
        id = "corp.shadowknight.skill.internal-ops"
        kind = "skill"
        title = "Internal Ops"
        privacy = "corp-private"
        """,
    )
    write(corp / "org" / "skills" / "internal-ops" / "body.md", "Internal ops body")
    write(
        corp / "org" / "policies" / "no-leaks" / "item.toml",
        """
        id = "corp.shadowknight.policy.no-leaks"
        kind = "policy"
        title = "No Leaks"
        privacy = "repo-safe"
        """,
    )
    write(corp / "org" / "policies" / "no-leaks" / "body.md", "Do not leak private corp process.")
    write(
        corp / "org" / "docs" / "internal-runbook" / "item.toml",
        """
        id = "corp.shadowknight.doc.internal-runbook"
        kind = "doc"
        title = "Internal Runbook"
        privacy = "corp-private"
        """,
    )
    write(corp / "org" / "docs" / "internal-runbook" / "body.md", "Internal runbook body")
    write(
        corp / "org" / "sources" / "shared-ext.toml",
        f"""
        id = "shared-ext"
        url = "{external_url}"
        commit = "{external_commit}"
        namespace = "shared"
        trust_mode = "pinned-commit"
        """,
    )
    write(
        corp / "repo-groups" / "platform" / "config.toml",
        """
        id = "platform"
        enabled_skills = ["corp.shadowknight.skill.platform-shared"]
        docs = ["corp.shadowknight.doc.platform-map"]
        recommended_agent_types = ["planner"]
        """,
    )
    write(
        corp / "repo-groups" / "platform" / "skills" / "platform-shared" / "item.toml",
        """
        id = "corp.shadowknight.skill.platform-shared"
        kind = "skill"
        title = "Platform Shared"
        privacy = "repo-safe"
        """,
    )
    write(corp / "repo-groups" / "platform" / "skills" / "platform-shared" / "body.md", "Platform shared body")
    write(
        corp / "repo-groups" / "platform" / "docs" / "platform-map" / "item.toml",
        """
        id = "corp.shadowknight.doc.platform-map"
        kind = "doc"
        title = "Platform Map"
        privacy = "repo-safe"
        """,
    )
    write(corp / "repo-groups" / "platform" / "docs" / "platform-map" / "body.md", "Platform map body")
    write(
        corp / "repos" / "internal-app" / "config.toml",
        f"""
        id = "internal-app"
        normalized_remotes = ["{internal_remote}"]
        repo_group_id = "platform"
        repo_class = "internal"
        enabled_skills = [
          "external.shared.skill.ext-review",
          "external.shared.skill.ext-lint",
          "corp.shadowknight.skill.internal-ops"
        ]
        optional_policies = ["external.shared.policy.ext-policy"]
        docs = ["corp.shadowknight.doc.internal-runbook"]

        [[item_override]]
        id = "external.shared.skill.ext-lint"
        timeout_seconds = 77
        """,
    )
    write(
        corp / "repos" / "internal-app" / "skills" / "ext-review" / "item.toml",
        """
        id = "external.shared.skill.ext-review"
        kind = "skill"
        title = "External Review Override"
        privacy = "repo-safe"
        timeout_seconds = 99
        source_note = "corp replacement"
        """,
    )
    write(corp / "repos" / "internal-app" / "skills" / "ext-review" / "body.md", "Internal replacement review body")
    write(
        corp / "repos" / "internal-alt" / "config.toml",
        f"""
        id = "internal-alt"
        normalized_remotes = ["{internal_alt_remote}"]
        repo_class = "internal"
        enabled_skills = ["corp.shadowknight.skill.shell-global"]
        """,
    )
    write(
        corp / "repos" / "client-private" / "config.toml",
        f"""
        id = "client-private"
        normalized_remotes = ["{client_private_remote}"]
        repo_class = "client"
        enabled_skills = ["corp.shadowknight.skill.internal-ops"]
        """,
    )
    write(
        corp / "repos" / "client-tracked" / "config.toml",
        f"""
        id = "client-tracked"
        normalized_remotes = ["{client_tracked_remote}"]
        repo_class = "client"
        enabled_skills = ["corp.shadowknight.skill.shell-global"]
        """,
    )
    write(
        corp / "indexes" / "repos.toml",
        """
        [[repo]]
        id = "client-private"
        path = "repos/client-private"

        [[repo]]
        id = "client-tracked"
        path = "repos/client-tracked"

        [[repo]]
        id = "internal-app"
        path = "repos/internal-app"

        [[repo]]
        id = "internal-alt"
        path = "repos/internal-alt"
        """,
    )
    write(
        corp / "indexes" / "repo-groups.toml",
        """
        [[repo_group]]
        id = "platform"
        path = "repo-groups/platform"
        """,
    )
    write(
        corp / "indexes" / "sources.toml",
        """
        [[source]]
        id = "shared-ext"
        path = "org/sources/shared-ext.toml"
        """,
    )
    return corp


def create_user_overrides(root: Path, workspace_binding_path: Path | None = None) -> Path:
    user = root / "user-overrides"
    binding_section = ""
    if workspace_binding_path is not None:
        binding_section = f"""

        [[workspace_binding]]
        name = "shared-non-git"
        path = "{workspace_binding_path.resolve()}"
        repo_group_id = "platform"
        """
    write(
        user / "config.toml",
        f"""
        id = "local"
        enabled_skills = ["user.local.skill.personal-shell"]
        preferred_agent_types = ["local-helper"]
        {binding_section}
        """,
    )
    write(
        user / "skills" / "personal-shell" / "item.toml",
        """
        id = "user.local.skill.personal-shell"
        kind = "skill"
        title = "Personal Shell"
        privacy = "repo-safe"
        """,
    )
    write(user / "skills" / "personal-shell" / "body.md", "Personal shell body")
    return user


class TeamAgentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.cache_root = self.home / ".team-agents" / "cache"
        self.internal_remote = "git.example.test/demo/internal-app"
        self.internal_alt_remote = "git.example.test/demo/internal-alt"
        self.client_private_remote = "git.example.test/demo/client-private"
        self.client_tracked_remote = "git.example.test/demo/client-tracked"
        self.external_url, self.external_commit = create_external_source_repo(self.root)
        self.personal_url, self.personal_commit = create_personal_source_repo(self.root)
        self.collision_url, self.collision_commit = create_collision_source_repo(self.root)
        self.alpha_url, self.alpha_commit = create_targeted_collision_source_repo(
            self.root,
            "alpha-source",
            "external.alpha.skill.shared-helper",
            "claude",
        )
        self.beta_url, self.beta_commit = create_targeted_collision_source_repo(
            self.root,
            "beta-source",
            "external.beta.skill.shared-helper",
            "codex",
        )
        self.bound_workspace = self.root / "non-git-bound"
        self.bound_workspace.mkdir()
        self.corp_repo = create_corp_repo(
            self.root,
            self.external_url,
            self.external_commit,
            self.internal_remote,
            self.internal_alt_remote,
            self.client_private_remote,
            self.client_tracked_remote,
        )
        self.user_overrides = create_user_overrides(self.root, workspace_binding_path=self.bound_workspace)
        self.internal_repo = self.root / "workspace-internal"
        self.client_private_repo = self.root / "workspace-client-private"
        self.client_tracked_repo = self.root / "workspace-client-tracked"
        self.unknown_repo = self.root / "workspace-unknown"
        init_repo(self.internal_repo, "git@git.example.test:demo/internal-app.git", tracked_agents="Manual intro")
        init_repo(self.client_private_repo, "https://git.example.test/demo/client-private.git")
        init_repo(self.client_tracked_repo, "https://git.example.test/demo/client-tracked.git", tracked_agents="Tracked client agents")
        init_repo(self.unknown_repo, "https://git.example.test/demo/unknown.git")

    def tearDown(self) -> None:
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()

    def configure_machine(self) -> MachineConfig:
        exit_code = main(
            [
                "setup",
                "--corp-repo",
                str(self.corp_repo),
                "--user-overrides",
                str(self.user_overrides),
                "--cache-root",
                str(self.cache_root),
            ]
        )
        self.assertEqual(exit_code, 0)
        return load_machine_config()

    def test_cli_no_longer_exposes_install_or_deploy_global(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["install"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["deploy-global"])

    def test_setup_writes_machine_config(self) -> None:
        config = self.configure_machine()
        self.assertEqual(config.corp_repo_path, self.corp_repo.resolve())
        self.assertEqual(config.user_override_path, self.user_overrides.resolve())
        self.assertTrue((self.home / ".team-agents" / "config.toml").exists())

    def test_setup_leaves_unregistered_workspace_unmaterialized(self) -> None:
        self.configure_machine()
        self.assertFalse((self.unknown_repo / ".agents").exists())
        self.assertFalse((self.unknown_repo / "AGENTS.md").exists())
        self.assertFalse((self.unknown_repo / "CLAUDE.md").exists())

    def test_context_command_outputs_resolution_json(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["context", "--workspace", str(self.unknown_repo), "--pretty"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["matched_repo_id"], None)
        self.assertIn("corp.shadowknight.skill.shell-global", payload["enabled_skills"])
        self.assertIn("user.local.skill.personal-shell", payload["enabled_skills"])

    def test_audit_command_reports_item_provenance(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["audit", "--workspace", str(self.internal_repo)])
        self.assertEqual(exit_code, 0)
        report = stdout.getvalue()
        self.assertIn("matched-repo: internal-app", report)
        self.assertIn("external.shared.skill.ext-review: skill replaced via repo", report)
        self.assertIn("corp.shadowknight.skill.internal-ops", report)

    def test_sync_internal_repo_writes_outputs_and_updates_agents(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        written = write_sync_output(result)
        self.assertTrue(any(path.name == "resolution.json" for path in written))
        agents_md = (self.internal_repo / "AGENTS.md").read_text(encoding="utf-8")
        claude_md = (self.internal_repo / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("<!-- team-agents:start -->", agents_md)
        self.assertIn("Use the local generated context under `.agents/`.", agents_md)
        self.assertIn("Use the local generated context under `.agents/`.", claude_md)
        self.assertTrue((self.internal_repo / ".agents" / "skills" / "ext-review" / "SKILL.md").exists())
        self.assertTrue((self.internal_repo / ".agents" / "skills" / "internal-ops" / "SKILL.md").exists())
        resolution = json.loads((self.internal_repo / ".agents" / "resolution.json").read_text(encoding="utf-8"))
        ext_review = resolution["items"]["external.shared.skill.ext-review"]
        self.assertEqual(ext_review["status"], "replaced")
        self.assertEqual(ext_review["replaced_from"]["source_ref"], self.external_commit)
        self.assertEqual(ext_review["body"], "Internal replacement review body\n")
        ext_lint = resolution["items"]["external.shared.skill.ext-lint"]
        self.assertEqual(ext_lint["timeout_seconds"], 77)
        self.assertIn("repo", ext_lint["overridden_by"])

    def test_sync_installs_git_exclude_protection(self) -> None:
        self.configure_machine()
        self.assertEqual(main(["sync", "--workspace", str(self.internal_repo)]), 0)
        exclude = (self.internal_repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertIn("/.agents/", exclude)
        self.assertIn("/CLAUDE.md", exclude)
        self.assertIn("/.cursor/rules/team-agents.mdc", exclude)

    def test_attach_registered_repo_auto_detects_and_syncs(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["attach", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["detected_kind"], "repo")
        self.assertEqual(payload["matched_repo_id"], "internal-app")
        self.assertTrue(payload["synced"])
        self.assertTrue((self.internal_repo / ".agents" / "index.md").exists())
        self.assertTrue(any(path.endswith(".agents/resolution.json") for path in payload["written"]))

    def test_attach_bound_workspace_auto_detects_and_syncs(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["attach", "--workspace", str(self.bound_workspace), "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["detected_kind"], "binding")
        self.assertEqual(payload["binding_name"], "shared-non-git")
        self.assertEqual(payload["matched_repo_group_id"], "platform")
        self.assertTrue(payload["synced"])
        self.assertTrue((self.bound_workspace / ".agents" / "resolution.json").exists())

    def test_attach_unresolved_repo_can_bind_to_existing_repo(self) -> None:
        machine = self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with patch("builtins.input", side_effect=["repo", "internal", "internal-app"]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["attach", "--workspace", str(self.unknown_repo)])
        self.assertEqual(exit_code, 0)
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        resolution = resolve_workspace(self.unknown_repo, machine, corp, user)
        self.assertEqual(resolution.workspace_context.matched_repo_id, "internal-app")
        config = (machine.user_override_path / "config.toml").read_text(encoding="utf-8")
        self.assertIn(f'path = "{self.unknown_repo.resolve()}"', config)
        self.assertIn('repo_id = "internal-app"', config)

    def test_attach_unresolved_repo_can_bind_to_existing_group(self) -> None:
        machine = self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with patch("builtins.input", side_effect=["group", "plat", "platform"]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["attach", "--workspace", str(self.unknown_repo)])
        self.assertEqual(exit_code, 0)
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        resolution = resolve_workspace(self.unknown_repo, machine, corp, user)
        self.assertEqual(resolution.workspace_context.matched_repo_group_id, "platform")
        self.assertIn("corp.shadowknight.skill.platform-shared", resolution.enabled_skills)

    def test_attach_unresolved_repo_can_use_baseline_only(self) -> None:
        machine = self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with patch("builtins.input", side_effect=[""]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["attach", "--workspace", str(self.unknown_repo)])
        self.assertEqual(exit_code, 0)
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        resolution = resolve_workspace(self.unknown_repo, machine, corp, user)
        self.assertTrue(resolution.workspace_context.is_unknown)
        self.assertTrue((self.unknown_repo / ".agents" / "resolution.json").exists())

    def test_attach_unresolved_repo_can_configure_now(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with patch("builtins.input", side_effect=["configure"]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["attach", "--workspace", str(self.unknown_repo)])
        self.assertEqual(exit_code, 0)
        config_path = self.corp_repo / "repos" / "unknown" / "config.toml"
        self.assertTrue(config_path.exists())
        self.assertTrue((self.unknown_repo / ".agents" / "resolution.json").exists())

    def test_sync_wraps_plain_skill_bodies_in_valid_frontmatter(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.unknown_repo, machine, corp, user)
        write_sync_output(result)
        shell_global = (self.unknown_repo / ".agents" / "skills" / "shell-global" / "SKILL.md").read_text(encoding="utf-8")
        personal_shell = (
            self.unknown_repo / ".agents" / "skills" / "personal-shell" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(shell_global.startswith("---\nname: "))
        self.assertIn('description: "Shell global body"', shell_global)
        self.assertIn("Shell global body", shell_global)
        self.assertTrue(personal_shell.startswith("---\nname: "))
        self.assertIn('description: "Personal shell body"', personal_shell)
        self.assertIn("Personal shell body", personal_shell)

    def test_sync_client_repo_fails_on_corp_private_skill(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        with self.assertRaises(ResolutionError):
            resolve_workspace(self.client_private_repo, machine, corp, user)

    def test_sync_client_repo_fails_on_tracked_agents_conflict(self) -> None:
        self.configure_machine()
        exit_code = main(["sync", "--workspace", str(self.client_tracked_repo)])
        self.assertEqual(exit_code, 1)

    def test_unknown_git_repo_gets_minimal_baseline_and_user_skill(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.unknown_repo, machine, corp, user)
        self.assertIsNone(result.workspace_context.matched_repo_id)
        self.assertEqual(
            set(result.enabled_skills),
            {"corp.shadowknight.skill.shell-global", "user.local.skill.personal-shell"},
        )
        self.assertNotIn("corp.shadowknight.doc.platform-map", result.active_docs)

    def test_non_git_workspace_binding_applies_repo_group_context(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.bound_workspace, machine, corp, user)
        self.assertEqual(result.workspace_context.matched_repo_group_id, "platform")
        self.assertIn("corp.shadowknight.skill.platform-shared", result.enabled_skills)
        self.assertIn("corp.shadowknight.doc.platform-map", result.active_docs)

    def test_duplicate_canonical_id_in_layer_fails_validation(self) -> None:
        write(
            self.corp_repo / "org" / "skills" / "shell-global-copy" / "item.toml",
            """
            id = "corp.shadowknight.skill.shell-global"
            kind = "skill"
            title = "Duplicate"
            privacy = "repo-safe"
            """,
        )
        write(self.corp_repo / "org" / "skills" / "shell-global-copy" / "body.md", "Duplicate body")
        with self.assertRaises(ValidationError):
            load_corp_repo(self.corp_repo)

    def test_user_override_cannot_disable_baseline_policy(self) -> None:
        write(
            self.user_overrides / "config.toml",
            """
            id = "local"
            enabled_skills = ["user.local.skill.personal-shell"]

            [[item_override]]
            id = "corp.shadowknight.policy.no-leaks"
            enabled = false
            """,
        )
        exit_code = main(
            [
                "setup",
                "--corp-repo",
                str(self.corp_repo),
                "--user-overrides",
                str(self.user_overrides),
                "--cache-root",
                str(self.cache_root),
            ]
        )
        self.assertEqual(exit_code, 1)

    def test_resolution_json_records_activation_provenance_across_layers(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        payload = resolve_workspace(self.internal_repo, machine, corp, user).to_dict()
        self.assertEqual(payload["items"]["corp.shadowknight.skill.shell-global"]["activated_by"], ["org:shadowknight"])
        self.assertEqual(payload["items"]["corp.shadowknight.skill.platform-shared"]["activated_by"], ["repo-group:platform"])
        self.assertEqual(payload["items"]["user.local.skill.personal-shell"]["activated_by"], ["user:local"])
        self.assertEqual(payload["items"]["corp.shadowknight.policy.no-leaks"]["activated_by"], ["org:shadowknight"])

    def test_user_layer_cannot_weaken_corp_private_item(self) -> None:
        write(
            self.user_overrides / "skills" / "internal-ops-replacement" / "item.toml",
            """
            id = "corp.shadowknight.skill.internal-ops"
            kind = "skill"
            title = "Weakened Internal Ops"
            privacy = "repo-safe"
            """,
        )
        write(
            self.user_overrides / "skills" / "internal-ops-replacement" / "body.md",
            "attempted weaker replacement",
        )
        write(
            self.user_overrides / "config.toml",
            """
            id = "local"
            enabled_skills = [
              "user.local.skill.personal-shell",
              "corp.shadowknight.skill.internal-ops"
            ]
            preferred_agent_types = ["local-helper"]
            """,
        )
        exit_code = main(
            [
                "setup",
                "--corp-repo",
                str(self.corp_repo),
                "--user-overrides",
                str(self.user_overrides),
                "--cache-root",
                str(self.cache_root),
            ]
        )
        self.assertEqual(exit_code, 1)

    def test_sync_refuses_when_generated_agents_content_is_tracked(self) -> None:
        write(self.internal_repo / ".agents" / "index.md", "tracked")
        git(self.internal_repo, "add", ".agents/index.md")
        git(self.internal_repo, "commit", "-m", "track generated path")
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        with self.assertRaisesRegex(ProtectionError, "Tracked .agents content already exists"):
            write_sync_output(result)

    def test_user_personal_source_is_pinned_and_loaded(self) -> None:
        write(
            self.user_overrides / "config.toml",
            """
            id = "local"
            enabled_sources = ["personal-remote-source"]
            enabled_skills = [
              "user.local.skill.personal-shell",
              "user.remote.skill.personal-remote"
            ]
            preferred_agent_types = ["local-helper"]
            """,
        )
        write(
            self.user_overrides / "sources" / "personal-remote-source.toml",
            f"""
            id = "personal-remote-source"
            url = "{self.personal_url}"
            commit = "{self.personal_commit}"
            namespace = "remote"
            trust_mode = "pinned-commit"
            """,
        )
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.unknown_repo, machine, corp, user)
        self.assertIn("personal-remote-source", result.enabled_sources)
        self.assertIn("user.remote.skill.personal-remote", result.enabled_skills)
        cached_checkout = machine.cache_root / "sources" / "personal-remote-source" / self.personal_commit / "checkout"
        self.assertTrue(cached_checkout.exists())
        library_link = self.home / ".team-agents" / "library" / "external" / f"personal-remote-source@{self.personal_commit}"
        self.assertTrue(library_link.is_symlink())
        self.assertEqual(library_link.resolve(), cached_checkout.resolve())
        trust_store = json.loads((machine.cache_root / "trust" / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(trust_store["sources"]["personal-remote-source"]["trust_mode"], "trust-on-first-use")

    def test_multi_remote_ambiguity_fails_explicitly(self) -> None:
        git(self.internal_repo, "remote", "add", "secondary", "https://git.example.test/demo/internal-alt.git")
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        with self.assertRaisesRegex(ResolutionError, "Multiple repo mappings matched remotes"):
            resolve_workspace(self.internal_repo, machine, corp, user)

    def test_invalid_repo_class_fails_validation(self) -> None:
        write(
            self.corp_repo / "repos" / "client-private" / "config.toml",
            f"""
            id = "client-private"
            normalized_remotes = ["{self.client_private_remote}"]
            repo_class = "bad"
            enabled_skills = ["corp.shadowknight.skill.internal-ops"]
            """,
        )
        with self.assertRaisesRegex(ValidationError, "Invalid repo_class"):
            load_corp_repo(self.corp_repo)

    def test_doctor_json_reports_failures_for_tracked_generated_content(self) -> None:
        write(self.internal_repo / ".agents" / "index.md", "tracked")
        git(self.internal_repo, "add", ".agents/index.md")
        git(self.internal_repo, "commit", "-m", "track generated path")
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 1)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["summary"]["fail"], 1)
        tracked_check = next(check for check in report["checks"] if check["name"] == "tracked-generated-content")
        self.assertEqual(tracked_check["status"], "fail")

    def test_doctor_json_reports_policy_compliance(self) -> None:
        write(
            self.corp_repo / "org" / "config.toml",
            """
            id = "shadowknight"
            enabled_sources = ["shared-ext"]
            enabled_skills = ["corp.shadowknight.skill.shell-global"]
            baseline_policies = [
              "corp.shadowknight.policy.no-leaks",
              "corp.shadowknight.policy.corp-compliance"
            ]
            recommended_agent_types = ["shell"]
            minimal_enabled_skills = ["corp.shadowknight.skill.shell-global"]
            protected_fields = ["baseline_policies", "privacy_rules"]
            """,
        )
        write(
            self.corp_repo / "org" / "policies" / "corp-compliance" / "item.toml",
            """
            id = "corp.shadowknight.policy.corp-compliance"
            kind = "policy"
            title = "Corp Compliance"
            privacy = "repo-safe"
            policy_rules = [
              { rule = "user_overrides_must_be_git_backed", severity = "warn", remediation = "Put user overrides under git" },
              { rule = "required_skill_ids", severity = "fail", skill_ids = ["corp.shadowknight.skill.missing"], remediation = "Enable the missing corp skill" },
              { rule = "forbidden_source_patterns", severity = "warn", patterns = ["shared-ext"], remediation = "Disable the forbidden source" }
            ]
            """,
        )
        write(
            self.corp_repo / "org" / "policies" / "corp-compliance" / "body.md",
            "Structured compliance policy",
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 1)
        report = json.loads(stdout.getvalue())
        self.assertIn("policy_compliance", report)
        entries = {entry["rule"]: entry for entry in report["policy_compliance"]}
        self.assertEqual(entries["user_overrides_must_be_git_backed"]["severity"], "warn")
        self.assertFalse(entries["user_overrides_must_be_git_backed"]["compliant"])
        self.assertFalse(entries["required_skill_ids"]["compliant"])
        self.assertIn("missing required skills", entries["required_skill_ids"]["detail"])
        self.assertFalse(entries["forbidden_source_patterns"]["compliant"])
        self.assertIn("remediation", entries["forbidden_source_patterns"])

    def test_client_resolution_json_does_not_inline_corp_private_bodies(self) -> None:
        write(
            self.corp_repo / "repos" / "client-private" / "config.toml",
            f"""
            id = "client-private"
            normalized_remotes = ["{self.client_private_remote}"]
            repo_class = "client"
            enabled_skills = ["corp.shadowknight.skill.shell-global"]
            """,
        )
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.client_private_repo, machine, corp, user)
        write_sync_output(result)
        payload = json.loads((self.client_private_repo / ".agents" / "resolution.json").read_text(encoding="utf-8"))
        shell_skill = payload["items"]["corp.shadowknight.skill.shell-global"]
        self.assertIn("body", shell_skill)
        for item in payload["items"].values():
            if item["privacy"] == "corp-private":
                self.assertNotIn("body", item)

    def test_internal_tracked_agents_without_markers_gets_managed_block_appended(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        write_sync_output(result)
        content = (self.internal_repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Manual intro", content)
        self.assertIn("<!-- team-agents:start -->", content)
        self.assertIn("<!-- team-agents:end -->", content)

    def test_corp_source_manifest_fingerprint_is_verified(self) -> None:
        manifest_path = self.corp_repo / "org" / "sources" / "shared-ext.toml"
        checkout_root = Path(self.external_url)
        digest = hashlib.sha256()
        for path in sorted(p for p in checkout_root.rglob("*") if p.is_file() and ".git" not in p.parts):
            digest.update(path.relative_to(checkout_root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        fingerprint = digest.hexdigest()
        write(
            manifest_path,
            f"""
            id = "shared-ext"
            url = "{self.external_url}"
            commit = "{self.external_commit}"
            namespace = "shared"
            trust_mode = "pinned-commit"
            fingerprint = "{fingerprint}"
            """,
        )
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        self.assertEqual(result.source_details["shared-ext"].trust_status, "verified-manifest-fingerprint")

    def test_init_commands_create_scaffolds(self) -> None:
        corp_dest = self.root / "generated-corp"
        user_dest = self.root / "generated-user"
        self.assertEqual(main(["init-corp-repo", "--dest", str(corp_dest)]), 0)
        self.assertEqual(main(["init-user-overrides", "--dest", str(user_dest)]), 0)
        self.assertTrue((corp_dest / "org" / "config.toml").exists())
        self.assertTrue((user_dest / "config.toml").exists())

    def test_setup_can_init_and_import_in_one_command(self) -> None:
        corp_dest = self.root / "combo-corp"
        user_dest = self.root / "combo-user"
        result = main(
            [
                "setup",
                "--corp-repo",
                str(corp_dest),
                "--user-overrides",
                str(user_dest),
                "--cache-root",
                str(self.cache_root),
                "--init-corp-if-missing",
                "--init-user-if-missing",
                "--import-codex-skills-from",
                str(self.root / "external-source"),  # no skills in native codex format, should still be safe
            ]
        )
        self.assertEqual(result, 0)
        self.assertTrue((corp_dest / "org" / "config.toml").exists())
        self.assertTrue((user_dest / "config.toml").exists())

    def test_setup_can_register_and_sync_workspace(self) -> None:
        corp_dest = self.root / "setup-corp"
        user_dest = self.root / "setup-user"
        result = main(
            [
                "setup",
                "--corp-repo",
                str(corp_dest),
                "--user-overrides",
                str(user_dest),
                "--cache-root",
                str(self.cache_root),
                "--init-corp-if-missing",
                "--init-user-if-missing",
                "--workspace",
                str(self.internal_repo),
                "--repo-id",
                "setup-internal",
                "--repo-class",
                "internal",
                "--sync",
            ]
        )
        self.assertEqual(result, 0)
        self.assertTrue((corp_dest / "repos" / "setup-internal" / "config.toml").exists())
        self.assertTrue((self.internal_repo / ".agents" / "index.md").exists())
        self.assertTrue((self.internal_repo / "AGENTS.md").exists())
        self.assertTrue((self.internal_repo / "CLAUDE.md").exists())

    def test_global_and_workspace_materialization_expose_same_skill(self) -> None:
        self.configure_machine()
        self.assertEqual(main(["sync", "--workspace", str(self.internal_repo)]), 0)
        global_skill = (self.home / ".claude" / "skills" / "shell-global" / "SKILL.md").read_text(encoding="utf-8")
        workspace_skill = (self.internal_repo / ".agents" / "skills" / "shell-global" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Shell global body", global_skill)
        self.assertIn("Shell global body", workspace_skill)

    def test_setup_can_import_codex_skills_into_org_layer(self) -> None:
        source_root = self.root / "codex-skills"
        write(source_root / "reviewer" / "SKILL.md", "# Reviewer")
        corp_dest = self.root / "import-corp"
        user_dest = self.root / "import-user"
        result = main(
            [
                "setup",
                "--corp-repo",
                str(corp_dest),
                "--user-overrides",
                str(user_dest),
                "--cache-root",
                str(self.cache_root),
                "--init-corp-if-missing",
                "--init-user-if-missing",
                "--import-codex-skills-from",
                str(source_root),
                "--import-codex-skills-to",
                "org",
            ]
        )
        self.assertEqual(result, 0)
        org_config = (corp_dest / "org" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('corp.example-org.skill.reviewer', org_config)
        self.assertTrue((corp_dest / "org" / "skills" / "reviewer" / "body.md").exists())

    def test_setup_reimport_cleans_old_managed_skills(self) -> None:
        source_root = self.root / "codex-skills"
        write(source_root / "reviewer" / "SKILL.md", "# Reviewer")
        corp_dest = self.root / "refresh-corp"
        user_dest = self.root / "refresh-user"
        result = main(
            [
                "setup",
                "--corp-repo",
                str(corp_dest),
                "--user-overrides",
                str(user_dest),
                "--cache-root",
                str(self.cache_root),
                "--init-corp-if-missing",
                "--init-user-if-missing",
                "--import-skills-from",
                str(source_root),
                "--import-skills-to",
                "user",
            ]
        )
        self.assertEqual(result, 0)
        self.assertTrue((user_dest / "skills" / "reviewer").exists())

        (source_root / "reviewer" / "SKILL.md").unlink()
        write(source_root / "linter" / "SKILL.md", "# Linter")
        result = main(
            [
                "setup",
                "--corp-repo",
                str(corp_dest),
                "--user-overrides",
                str(user_dest),
                "--cache-root",
                str(self.cache_root),
                "--import-skills-from",
                str(source_root),
                "--import-skills-to",
                "user",
            ]
        )
        self.assertEqual(result, 0)
        user_config = (user_dest / "config.toml").read_text(encoding="utf-8")
        self.assertFalse((user_dest / "skills" / "reviewer").exists())
        self.assertTrue((user_dest / "skills" / "linter").exists())
        self.assertNotIn("user.local.skill.reviewer", user_config)
        self.assertIn("user.local.skill.linter", user_config)

    def test_refresh_personal_skills_command_reimports_from_machine_source(self) -> None:
        machine = self.configure_machine()
        source_root = self.root / "codex-skills"
        write(source_root / "reviewer" / "SKILL.md", "# Reviewer")
        result = main(["refresh-personal-skills", "--source", str(source_root)])
        self.assertEqual(result, 0)
        self.assertTrue((machine.user_override_path / "skills" / "reviewer").exists())

        (source_root / "reviewer" / "SKILL.md").unlink()
        write(source_root / "linter" / "SKILL.md", "# Linter")
        result = main(["refresh-personal-skills", "--source", str(source_root)])
        self.assertEqual(result, 0)
        user_config = (machine.user_override_path / "config.toml").read_text(encoding="utf-8")
        self.assertFalse((machine.user_override_path / "skills" / "reviewer").exists())
        self.assertTrue((machine.user_override_path / "skills" / "linter").exists())
        self.assertNotIn("user.local.skill.reviewer", user_config)
        self.assertIn("user.local.skill.linter", user_config)

    def test_onboard_repo_registers_repo_group_and_syncs(self) -> None:
        self.configure_machine()
        fresh_repo = self.root / "workspace-new"
        init_repo(fresh_repo, "https://git.example.test/demo/new-client.git")
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "onboard-repo",
                    "--workspace",
                    str(fresh_repo),
                    "--repo-id",
                    "new-client",
                    "--repo-class",
                    "internal",
                    "--repo-group-id",
                    "platform",
                    "--enable-skill",
                    "corp.shadowknight.skill.platform-shared",
                    "--enable-doc",
                    "corp.shadowknight.doc.platform-map",
                    "--recommended-agent-type",
                    "planner",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["synced"])
        config = (self.corp_repo / "repos" / "new-client" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('repo_group_id = "platform"', config)
        self.assertIn('enabled_skills = ["corp.shadowknight.skill.platform-shared"]', config)
        self.assertTrue((fresh_repo / ".agents" / "index.md").exists())

    def test_configure_repo_creates_repo_layer_config_from_current_workspace(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "configure-repo",
                    "--workspace",
                    str(self.unknown_repo),
                    "--repo-id",
                    "unknown-service",
                    "--repo-class",
                    "internal",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "created")
        self.assertEqual(payload["repo_id"], "unknown-service")
        self.assertTrue(payload["synced"])
        config = (self.corp_repo / "repos" / "unknown-service" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('id = "unknown-service"', config)
        self.assertIn('repo_class = "internal"', config)
        self.assertTrue((self.unknown_repo / ".agents" / "index.md").exists())

    def test_configure_repo_updates_existing_registered_repo_instead_of_failing(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "configure-repo",
                    "--workspace",
                    str(self.internal_repo),
                    "--repo-group-id",
                    "platform",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "updated")
        self.assertEqual(payload["repo_id"], "internal-app")
        self.assertEqual(payload["repo_group_id"], "platform")
        self.assertTrue(payload["synced"])
        config = (self.corp_repo / "repos" / "internal-app" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('repo_group_id = "platform"', config)
        self.assertTrue((self.internal_repo / ".agents" / "resolution.json").exists())

    def test_configure_repo_edits_repo_layer_deltas_without_copy_down(self) -> None:
        machine = self.configure_machine()
        internal_alt_repo = self.root / "workspace-internal-alt"
        init_repo(internal_alt_repo, "https://git.example.test/demo/internal-alt.git")
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "configure-repo",
                    "--workspace",
                    str(internal_alt_repo),
                    "--enable-skill",
                    "corp.shadowknight.skill.internal-ops",
                    "--disable-skill",
                    "corp.shadowknight.skill.shell-global",
                    "--disable-source",
                    "shared-ext",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("corp.shadowknight.skill.internal-ops", payload["repo_layer"]["enabled_skills"])
        self.assertIn("corp.shadowknight.skill.shell-global", payload["repo_layer"]["disabled_skills"])
        self.assertIn("shared-ext", payload["repo_layer"]["disabled_sources"])
        self.assertIn("corp.shadowknight.skill.internal-ops", payload["effective"]["enabled_skills"])
        self.assertNotIn("corp.shadowknight.skill.shell-global", payload["effective"]["enabled_skills"])
        self.assertNotIn("shared-ext", payload["effective"]["enabled_sources"])

        config = (machine.corp_repo_path / "repos" / "internal-alt" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('enabled_skills = ["corp.shadowknight.skill.internal-ops"]', config)
        self.assertIn('disabled_skills = ["corp.shadowknight.skill.shell-global"]', config)
        self.assertIn('disabled_sources = ["shared-ext"]', config)
        self.assertNotIn("corp.shadowknight.skill.platform-shared", config)

    def test_configure_repo_rejects_overlapping_skill_slug_collision_in_json_mode(self) -> None:
        self.configure_machine()
        internal_alt_repo = self.root / "workspace-internal-alt"
        init_repo(internal_alt_repo, "https://git.example.test/demo/internal-alt.git")
        self.assertEqual(
            main(
                [
                    "add-source",
                    "--layer",
                    "org",
                    "--source-id",
                    "collision-ext",
                    "--url",
                    self.collision_url,
                    "--commit",
                    self.collision_commit,
                    "--namespace",
                    "collision",
                ]
            ),
            0,
        )
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "configure-repo",
                    "--workspace",
                    str(internal_alt_repo),
                    "--enable-source",
                    "collision-ext",
                    "--enable-skill",
                    "external.shared.skill.ext-review",
                    "--enable-skill",
                    "external.collision.skill.ext-review",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 1)
        self.assertIn("Skill emission collisions must be resolved before apply", stderr.getvalue())

    def test_configure_repo_interactively_resolves_collision_by_disabling_loser(self) -> None:
        machine = self.configure_machine()
        internal_alt_repo = self.root / "workspace-internal-alt"
        init_repo(internal_alt_repo, "https://git.example.test/demo/internal-alt.git")
        self.assertEqual(
            main(
                [
                    "add-source",
                    "--layer",
                    "org",
                    "--source-id",
                    "collision-ext",
                    "--url",
                    self.collision_url,
                    "--commit",
                    self.collision_commit,
                    "--namespace",
                    "collision",
                ]
            ),
            0,
        )
        stdout = StringIO()
        stderr = StringIO()
        with patch("builtins.input", side_effect=["external.collision.skill.ext-review"]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "configure-repo",
                        "--workspace",
                        str(internal_alt_repo),
                        "--enable-source",
                        "collision-ext",
                        "--enable-skill",
                        "external.shared.skill.ext-review",
                        "--enable-skill",
                        "external.collision.skill.ext-review",
                    ]
                )
        self.assertEqual(exit_code, 0)
        config = (machine.corp_repo_path / "repos" / "internal-alt" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('disabled_skills = ["external.shared.skill.ext-review"]', config)
        self.assertIn('external.collision.skill.ext-review', config)

    def test_configure_repo_allows_same_slug_when_tool_targets_do_not_overlap(self) -> None:
        machine = self.configure_machine()
        internal_alt_repo = self.root / "workspace-internal-alt"
        init_repo(internal_alt_repo, "https://git.example.test/demo/internal-alt.git")
        self.assertEqual(
            main(
                [
                    "add-source",
                    "--layer",
                    "org",
                    "--source-id",
                    "alpha-ext",
                    "--url",
                    self.alpha_url,
                    "--commit",
                    self.alpha_commit,
                    "--namespace",
                    "alpha",
                ]
            ),
            0,
        )
        self.assertEqual(
            main(
                [
                    "add-source",
                    "--layer",
                    "org",
                    "--source-id",
                    "beta-ext",
                    "--url",
                    self.beta_url,
                    "--commit",
                    self.beta_commit,
                    "--namespace",
                    "beta",
                ]
            ),
            0,
        )
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "configure-repo",
                    "--workspace",
                    str(internal_alt_repo),
                    "--enable-source",
                    "alpha-ext",
                    "--enable-source",
                    "beta-ext",
                    "--enable-skill",
                    "external.alpha.skill.shared-helper",
                    "--enable-skill",
                    "external.beta.skill.shared-helper",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("external.alpha.skill.shared-helper", payload["effective"]["enabled_skills"])
        self.assertIn("external.beta.skill.shared-helper", payload["effective"]["enabled_skills"])

    def test_configure_group_creates_group_and_links_current_repo(self) -> None:
        machine = self.configure_machine()
        internal_alt_repo = self.root / "workspace-internal-alt"
        init_repo(internal_alt_repo, "https://git.example.test/demo/internal-alt.git")
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "configure-group",
                    "--workspace",
                    str(internal_alt_repo),
                    "--group-id",
                    "ops-cluster",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "created")
        self.assertEqual(payload["repo_id"], "internal-alt")
        self.assertEqual(payload["group_id"], "ops-cluster")
        self.assertTrue(payload["synced"])

        group_config = (machine.corp_repo_path / "repo-groups" / "ops-cluster" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('id = "ops-cluster"', group_config)
        repo_config = (machine.corp_repo_path / "repos" / "internal-alt" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('repo_group_id = "ops-cluster"', repo_config)

    def test_configure_group_updates_existing_group_layer_deltas_and_sources(self) -> None:
        machine = self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "configure-group",
                    "--workspace",
                    str(self.internal_repo),
                    "--enable-skill",
                    "corp.shadowknight.skill.internal-ops",
                    "--disable-skill",
                    "corp.shadowknight.skill.platform-shared",
                    "--enable-source",
                    "shared-ext",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "updated")
        self.assertEqual(payload["group_id"], "platform")
        self.assertIn("corp.shadowknight.skill.internal-ops", payload["group_layer"]["enabled_skills"])
        self.assertIn("corp.shadowknight.skill.platform-shared", payload["group_layer"]["disabled_skills"])
        self.assertIn("shared-ext", payload["group_layer"]["enabled_sources"])
        self.assertIn("corp.shadowknight.skill.internal-ops", payload["effective"]["enabled_skills"])
        self.assertNotIn("corp.shadowknight.skill.platform-shared", payload["effective"]["enabled_skills"])
        self.assertIn("shared-ext", payload["effective"]["enabled_sources"])

        group_config = (machine.corp_repo_path / "repo-groups" / "platform" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('enabled_skills = ["corp.shadowknight.skill.internal-ops"]', group_config)
        self.assertIn('disabled_skills = ["corp.shadowknight.skill.platform-shared"]', group_config)
        self.assertIn('enabled_sources = ["shared-ext"]', group_config)

    def test_complete_skill_disables_one_time_skill_at_repo_scope(self) -> None:
        machine = self.configure_machine()
        self.assertEqual(
            main(
                [
                    "configure-repo",
                    "--workspace",
                    str(self.internal_repo),
                    "--enable-skill",
                    "corp.shadowknight.skill.repo-onboarding",
                    "--json",
                ]
            ),
            0,
        )
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "complete-skill",
                    "corp.shadowknight.skill.repo-onboarding",
                    "--workspace",
                    str(self.internal_repo),
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["scope"], "repo")
        self.assertNotIn("corp.shadowknight.skill.repo-onboarding", payload["enabled_skills"])
        repo_config = (machine.corp_repo_path / "repos" / "internal-app" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('disabled_skills = ["corp.shadowknight.skill.repo-onboarding"]', repo_config)

    def test_complete_skill_disables_one_time_skill_at_binding_scope(self) -> None:
        machine = self.configure_machine()
        platform_config_path = machine.corp_repo_path / "repo-groups" / "platform" / "config.toml"
        platform_config = platform_config_path.read_text(encoding="utf-8")
        platform_config_path.write_text(
            platform_config.replace(
                'enabled_skills = ["corp.shadowknight.skill.platform-shared"]',
                'enabled_skills = ["corp.shadowknight.skill.platform-shared", "corp.shadowknight.skill.repo-onboarding"]',
            ),
            encoding="utf-8",
        )
        bound = self.root / "bound-onboarding"
        bound.mkdir()
        self.assertEqual(
            main(
                [
                    "bind-workspace",
                    "--path",
                    str(bound),
                    "--name",
                    "bound-onboarding",
                    "--repo-group-id",
                    "platform",
                ]
            ),
            0,
        )
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "complete-skill",
                    "corp.shadowknight.skill.repo-onboarding",
                    "--workspace",
                    str(bound),
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["scope"], "binding")
        self.assertNotIn("corp.shadowknight.skill.repo-onboarding", payload["enabled_skills"])
        user_config = machine.user_override_path / "config.toml"
        self.assertIn('disabled_skills = ["corp.shadowknight.skill.repo-onboarding"]', user_config.read_text(encoding="utf-8"))

    def test_onboard_repo_prompts_for_missing_values(self) -> None:
        self.configure_machine()
        fresh_repo = self.root / "workspace-prompted"
        init_repo(fresh_repo, "https://git.example.test/demo/prompted-service.git")
        answers = [
            "",  # repo id -> derived default
            "",  # repo class -> internal
            "platform",
            "corp.shadowknight.skill.platform-shared",
            "",
            "corp.shadowknight.doc.platform-map",
            "planner",
        ]
        stdout = StringIO()
        stderr = StringIO()
        with patch("builtins.input", side_effect=answers):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "onboard-repo",
                        "--workspace",
                        str(fresh_repo),
                        "--json",
                    ]
                )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["repo_id"], "prompted-service")
        self.assertEqual(payload["repo_group_id"], "platform")
        self.assertIn("corp.shadowknight.skill.platform-shared", payload["enabled_skills"])
        self.assertIn("corp.shadowknight.doc.platform-map", payload["docs"])
        self.assertIn("planner", payload["recommended_agent_types"])
        self.assertTrue((fresh_repo / ".agents" / "index.md").exists())

    def test_bind_workspace_command_writes_binding_used_by_resolution(self) -> None:
        machine = self.configure_machine()
        bound = self.root / "bound-later"
        bound.mkdir()
        result = main(
            [
                "bind-workspace",
                "--path",
                str(bound),
                "--name",
                "bound-later",
                "--repo-group-id",
                "platform",
            ]
        )
        self.assertEqual(result, 0)
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        resolution = resolve_workspace(bound, machine, corp, user)
        self.assertEqual(resolution.workspace_context.matched_repo_group_id, "platform")
        self.assertIn("corp.shadowknight.skill.platform-shared", resolution.enabled_skills)
        self.assertTrue((bound / ".agents" / "resolution.json").exists())

    def test_bind_workspace_prompts_for_missing_values(self) -> None:
        machine = self.configure_machine()
        bound = self.root / "bound-prompted"
        bound.mkdir()
        answers = [
            "",  # binding name -> default path name
            "",  # target kind -> repo-group
            "platform",
        ]
        stdout = StringIO()
        stderr = StringIO()
        with patch("builtins.input", side_effect=answers):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "bind-workspace",
                        "--path",
                        str(bound),
                        "--json",
                    ]
                )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["name"], "bound-prompted")
        self.assertEqual(payload["repo_group_id"], "platform")
        self.assertTrue(payload["synced"])
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        resolution = resolve_workspace(bound, machine, corp, user)
        self.assertEqual(resolution.workspace_context.matched_repo_group_id, "platform")
        self.assertTrue((bound / ".agents" / "resolution.json").exists())

    def test_setup_can_add_and_enable_repo_source(self) -> None:
        corp_dest = self.root / "source-corp"
        user_dest = self.root / "source-user"
        result = main(
            [
                "setup",
                "--corp-repo",
                str(corp_dest),
                "--user-overrides",
                str(user_dest),
                "--cache-root",
                str(self.cache_root),
                "--init-corp-if-missing",
                "--init-user-if-missing",
                "--workspace",
                str(self.internal_repo),
                "--repo-id",
                "source-internal",
                "--repo-class",
                "internal",
                "--add-and-enable-source",
                "repo",
                "shared-second",
                self.external_url,
                self.external_commit,
                "shared",
            ]
        )
        self.assertEqual(result, 0)
        manifest = corp_dest / "org" / "sources" / "shared-second.toml"
        self.assertTrue(manifest.exists())
        repo_config = (corp_dest / "repos" / "source-internal" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('enabled_sources = ["shared-second"]', repo_config)

    def test_add_source_rejects_same_url_different_commit_without_explicit_choice(self) -> None:
        self.configure_machine()
        write(self.root / "external-source" / "README.md", "next pin")
        git(self.root / "external-source", "add", "README.md")
        git(self.root / "external-source", "commit", "-m", "next pin")
        next_commit = git(self.root / "external-source", "rev-parse", "HEAD")
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "add-source",
                    "--layer",
                    "org",
                    "--source-id",
                    "shared-next",
                    "--url",
                    self.external_url,
                    "--commit",
                    next_commit,
                    "--namespace",
                    "shared",
                ]
            )
        self.assertEqual(exit_code, 1)
        self.assertIn("already approved at another pin", stderr.getvalue())

    def test_add_source_can_create_parallel_pin_track_explicitly(self) -> None:
        self.configure_machine()
        write(self.root / "external-source" / "README.md", "parallel pin")
        git(self.root / "external-source", "add", "README.md")
        git(self.root / "external-source", "commit", "-m", "parallel pin")
        next_commit = git(self.root / "external-source", "rev-parse", "HEAD")
        result = main(
            [
                "add-source",
                "--layer",
                "org",
                "--source-id",
                "shared-next",
                "--url",
                self.external_url,
                "--commit",
                next_commit,
                "--namespace",
                "shared-next",
                "--allow-parallel-pin",
            ]
        )
        self.assertEqual(result, 0)
        manifest = (self.corp_repo / "org" / "sources" / "shared-next.toml").read_text(encoding="utf-8")
        self.assertIn(f'commit = "{next_commit}"', manifest)
        index = (self.corp_repo / "indexes" / "sources.toml").read_text(encoding="utf-8")
        self.assertIn('id = "shared-ext"', index)
        self.assertIn('id = "shared-next"', index)

    def test_add_source_can_update_existing_pin_track_explicitly(self) -> None:
        self.configure_machine()
        write(self.root / "external-source" / "README.md", "updated pin")
        git(self.root / "external-source", "add", "README.md")
        git(self.root / "external-source", "commit", "-m", "updated pin")
        next_commit = git(self.root / "external-source", "rev-parse", "HEAD")
        result = main(
            [
                "add-source",
                "--layer",
                "org",
                "--source-id",
                "shared-ext",
                "--url",
                self.external_url,
                "--commit",
                next_commit,
                "--namespace",
                "shared",
                "--update-existing-source-id",
                "shared-ext",
            ]
        )
        self.assertEqual(result, 0)
        manifest = (self.corp_repo / "org" / "sources" / "shared-ext.toml").read_text(encoding="utf-8")
        self.assertIn(f'commit = "{next_commit}"', manifest)
        index = (self.corp_repo / "indexes" / "sources.toml").read_text(encoding="utf-8")
        self.assertEqual(index.count('id = "shared-ext"'), 1)

    def test_promote_skills_moves_bootstrapped_user_skill_to_org(self) -> None:
        source_root = self.root / "codex-skills"
        write(source_root / "reviewer" / "SKILL.md", "# Reviewer\n")
        write(source_root / "reviewer" / "notes.md", "review notes")
        corp_dest = self.root / "promote-corp"
        user_dest = self.root / "promote-user"
        result = main(
            [
                "setup",
                "--corp-repo",
                str(corp_dest),
                "--user-overrides",
                str(user_dest),
                "--cache-root",
                str(self.cache_root),
                "--init-corp-if-missing",
                "--init-user-if-missing",
                "--import-skills-from",
                str(source_root),
                "--import-skills-to",
                "user",
            ]
        )
        self.assertEqual(result, 0)
        promote_result = main(
            [
                "promote-skills",
                "--from-layer",
                "user",
                "--to-layer",
                "org",
                "--all-imported",
            ]
        )
        self.assertEqual(promote_result, 0)
        user_config = (user_dest / "config.toml").read_text(encoding="utf-8")
        org_config = (corp_dest / "org" / "config.toml").read_text(encoding="utf-8")
        self.assertNotIn("user.local.skill.reviewer", user_config)
        self.assertIn("corp.example-org.skill.reviewer", org_config)
        self.assertFalse((user_dest / "skills" / "reviewer").exists())
        self.assertTrue((corp_dest / "org" / "skills" / "reviewer").exists())
        body = (corp_dest / "org" / "skills" / "reviewer" / "body.md").read_text(encoding="utf-8")
        self.assertIn("corp.example-org.doc.reviewer-notes-md", body)
        doc_item = (corp_dest / "org" / "docs" / "reviewer-notes-md" / "item.toml").read_text(encoding="utf-8")
        self.assertIn('id = "corp.example-org.doc.reviewer-notes-md"', doc_item)

    def test_register_repo_creates_mapping(self) -> None:
        machine = self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "register-repo",
                    "--workspace",
                    str(self.internal_repo),
                    "--repo-id",
                    "local-internal",
                    "--repo-class",
                    "internal",
                ]
            )
        self.assertEqual(exit_code, 0)
        config_path = machine.corp_repo_path / "repos" / "local-internal" / "config.toml"
        self.assertTrue(config_path.exists())
        index_content = (machine.corp_repo_path / "indexes" / "repos.toml").read_text(encoding="utf-8")
        self.assertIn('id = "local-internal"', index_content)

    def test_migrate_user_overrides_moves_legacy_tree_and_is_idempotent(self) -> None:
        legacy_root = self.home / ".team-agents-user"
        write(
            legacy_root / "config.toml",
            """
            id = "legacy"
            enabled_skills = ["user.legacy.skill.legacy-review"]
            """,
        )
        write(
            legacy_root / "skills" / "legacy-review" / "item.toml",
            """
            id = "user.legacy.skill.legacy-review"
            kind = "skill"
            title = "Legacy Review"
            privacy = "repo-safe"
            """,
        )
        write(legacy_root / "skills" / "legacy-review" / "body.md", "legacy review body")
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(
                [
                    "migrate-user-overrides",
                    "--user",
                    "legacy",
                    "--corp-repo",
                    str(self.corp_repo),
                    "--cache-root",
                    str(self.cache_root),
                    "--json",
                ]
            )
        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        migrated_skill = self.corp_repo / "users" / "legacy" / "skills" / "legacy-review" / "body.md"
        self.assertTrue(migrated_skill.exists())
        self.assertTrue(payload["moved"])
        self.assertTrue((self.cache_root / "logs" / "migrations" / "migrate-user-overrides-legacy.json").exists())

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(
                [
                    "migrate-user-overrides",
                    "--user",
                    "legacy",
                    "--corp-repo",
                    str(self.corp_repo),
                    "--cache-root",
                    str(self.cache_root),
                    "--json",
                ]
            )
        self.assertEqual(result, 0)
        rerun = json.loads(stdout.getvalue())
        self.assertTrue(rerun["skipped"])

        setup_result = main(
            [
                "setup",
                "--corp-repo",
                str(self.corp_repo),
                "--user",
                "legacy",
                "--cache-root",
                str(self.cache_root),
            ]
        )
        self.assertEqual(setup_result, 0)
        global_skill = (self.home / ".claude" / "skills" / "legacy-review" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("legacy review body", global_skill)

    def test_update_refreshes_user_global_and_recent_workspace_outputs(self) -> None:
        git(self.corp_repo, "init")
        git(self.corp_repo, "config", "user.email", "test@example.com")
        git(self.corp_repo, "config", "user.name", "Test User")
        git(self.corp_repo, "add", ".")
        git(self.corp_repo, "commit", "-m", "corp init")
        corp_remote = self.root / "corp-remote.git"
        subprocess.run(["git", "init", "--bare", str(corp_remote)], check=True, capture_output=True, text=True)
        git(self.corp_repo, "remote", "add", "origin", str(corp_remote))
        git(self.corp_repo, "push", "-u", "origin", "HEAD")
        corp_clone = self.root / "corp-clone"
        subprocess.run(["git", "clone", str(corp_remote), str(corp_clone)], check=True, capture_output=True, text=True)

        exit_code = main(
            [
                "setup",
                "--corp-repo",
                str(corp_clone),
                "--user-overrides",
                str(self.user_overrides),
                "--cache-root",
                str(self.cache_root),
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(main(["sync", "--workspace", str(self.internal_repo)]), 0)
        global_skill_path = self.home / ".claude" / "skills" / "shell-global" / "SKILL.md"
        self.assertIn("Shell global body", global_skill_path.read_text(encoding="utf-8"))

        write(self.corp_repo / "org" / "skills" / "shell-global" / "body.md", "Updated shell global body")
        git(self.corp_repo, "add", "org/skills/shell-global/body.md")
        git(self.corp_repo, "commit", "-m", "update shell global")
        git(self.corp_repo, "push")

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["update", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("corp_before_commit", payload)
        self.assertIn("corp_after_commit", payload)
        self.assertTrue((self.cache_root / "logs" / "update.json").exists())
        self.assertIn("Updated shell global body", global_skill_path.read_text(encoding="utf-8"))
        workspace_skill = (self.internal_repo / ".agents" / "skills" / "shell-global" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Updated shell global body", workspace_skill)


if __name__ == "__main__":
    unittest.main()
