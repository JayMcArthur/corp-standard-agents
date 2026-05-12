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

from team_agents.cli import main
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
        self.internal_remote = "github.com/acme/internal-app"
        self.internal_alt_remote = "github.com/acme/internal-alt"
        self.client_private_remote = "github.com/acme/client-private"
        self.client_tracked_remote = "github.com/acme/client-tracked"
        self.external_url, self.external_commit = create_external_source_repo(self.root)
        self.personal_url, self.personal_commit = create_personal_source_repo(self.root)
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
        init_repo(self.internal_repo, "git@github.com:acme/internal-app.git", tracked_agents="Manual intro")
        init_repo(self.client_private_repo, "https://github.com/acme/client-private.git")
        init_repo(self.client_tracked_repo, "https://github.com/acme/client-tracked.git", tracked_agents="Tracked client agents")
        init_repo(self.unknown_repo, "https://github.com/acme/unknown.git")

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

    def test_setup_writes_machine_config(self) -> None:
        config = self.configure_machine()
        self.assertEqual(config.corp_repo_path, self.corp_repo.resolve())
        self.assertEqual(config.user_override_path, self.user_overrides.resolve())
        self.assertTrue((self.home / ".team-agents" / "config.toml").exists())

    def test_sync_internal_repo_writes_outputs_and_updates_agents(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        written = write_sync_output(result)
        self.assertTrue(any(path.name == "resolution.json" for path in written))
        agents_md = (self.internal_repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("<!-- team-agents:start -->", agents_md)
        self.assertIn("Use the local generated context under `.agents/`.", agents_md)
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
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_overrides(machine.user_override_path)
        with self.assertRaises(ResolutionError):
            resolve_workspace(self.internal_repo, machine, corp, user)

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
        trust_store = json.loads((machine.cache_root / "trust" / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(trust_store["sources"]["personal-remote-source"]["trust_mode"], "trust-on-first-use")

    def test_multi_remote_ambiguity_fails_explicitly(self) -> None:
        git(self.internal_repo, "remote", "add", "secondary", "https://github.com/acme/internal-alt.git")
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


if __name__ == "__main__":
    unittest.main()
