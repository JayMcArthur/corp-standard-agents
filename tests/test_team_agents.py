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
from team_agents.loaders import load_corp_repo, load_user_layer
from team_agents.machine import load_machine_config
from team_agents.models import MachineConfig
from team_agents.output import write_sync_output
from team_agents.resolution_schema import validate_resolution_json
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
        corp / "org" / "contexts" / "internal-runbook" / "item.toml",
        """
        id = "corp.shadowknight.context.internal-runbook"
        kind = "context"
        title = "Internal Runbook"
        privacy = "corp-private"
        """,
    )
    write(corp / "org" / "contexts" / "internal-runbook" / "body.md", "Internal runbook body")
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
        contexts = ["corp.shadowknight.context.platform-map"]
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
        corp / "repo-groups" / "platform" / "contexts" / "platform-map" / "item.toml",
        """
        id = "corp.shadowknight.context.platform-map"
        kind = "context"
        title = "Platform Map"
        privacy = "repo-safe"
        """,
    )
    write(corp / "repo-groups" / "platform" / "contexts" / "platform-map" / "body.md", "Platform map body")
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
        contexts = ["corp.shadowknight.context.internal-runbook"]

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


def create_user_layer(root: Path, workspace_binding_path: Path | None = None) -> Path:
    user = root / "user-layer"
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
        self.user_layer = create_user_layer(self.root, workspace_binding_path=self.bound_workspace)
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
                "--user-path",
                str(self.user_layer),
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
        self.assertEqual(config.user_layer_path, self.user_layer.resolve())
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
        validate_resolution_json(payload)
        self.assertEqual(payload["matched_repo_id"], None)
        self.assertNotIn("consumer_safety_warnings", payload)
        self.assertIn("corp.shadowknight.skill.shell-global", payload["enabled_skills"])
        self.assertIn("user.local.skill.personal-shell", payload["enabled_skills"])
        shell = payload["items"]["corp.shadowknight.skill.shell-global"]
        self.assertEqual(shell["kind"], "skill")
        self.assertEqual(shell["title"], "Shell Global")
        self.assertEqual(shell["source_type"], "corp")
        self.assertIn("source_path", shell)
        self.assertEqual(shell["activation_state"], "enabled")
        self.assertFalse(shell["required"])
        self.assertEqual(shell["selected_by_packs"], [])
        self.assertEqual(shell["selected_by_profiles"], [])
        self.assertEqual(shell["target_outputs"], ["claude", "codex", "cursor"])
        self.assertEqual(shell["privacy_status"], "repo-safe")

    def test_context_for_harness_outputs_structured_constraints_without_orchestration(self) -> None:
        write(
            self.corp_repo / "org" / "profiles" / "runner.toml",
            """
            id = "runner"
            stop_conditions = ["secrets_detected"]

            [activation]
            required = ["corp.shadowknight.completion_gate.definition-of-done"]
            enabled = ["corp.shadowknight.playbook.prep-before-code"]
            """,
        )
        write(
            self.corp_repo / "org" / "completion_gates" / "definition-of-done" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.definition-of-done"
            kind = "completion_gate"
            title = "Definition Of Done"
            privacy = "repo-safe"
            evidence_required = ["tests_run", "risk_notes"]
            """,
        )
        write(self.corp_repo / "org" / "completion_gates" / "definition-of-done" / "body.md", "Show evidence before done.")
        write(
            self.corp_repo / "org" / "playbooks" / "prep-before-code" / "item.toml",
            """
            id = "corp.shadowknight.playbook.prep-before-code"
            kind = "playbook"
            title = "Prep Before Code"
            privacy = "repo-safe"
            inputs = ["task_request", "repo_context"]
            outputs = ["implementation_plan", "verification_plan"]
            evidence_required = ["verification_plan"]
            stop_conditions = ["ambiguous_requirement"]
            """,
        )
        write(self.corp_repo / "org" / "playbooks" / "prep-before-code" / "body.md", "Plan before implementation.")
        write(
            self.corp_repo / "org" / "config.toml",
            """
            id = "shadowknight"
            enabled_sources = ["shared-ext"]
            enabled_skills = ["corp.shadowknight.skill.shell-global"]
            baseline_policies = ["corp.shadowknight.policy.no-leaks"]
            allowed_profiles = ["runner"]
            default_profile = "runner"
            recommended_agent_types = ["shell"]
            minimal_enabled_skills = ["corp.shadowknight.skill.shell-global"]
            protected_fields = ["baseline_policies", "privacy_rules"]
            """,
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["context", "--workspace", str(self.internal_repo), "--for-harness", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["kind"], "harness-context")
        self.assertIn("no task runner", payload["non_goals"])
        self.assertEqual(payload["workspace"]["profile"], "runner")
        self.assertIn("corp.shadowknight.completion_gate.definition-of-done", payload["required_completion_gates"])
        self.assertIn("corp.shadowknight.completion_gate.definition-of-done", payload["evidence_requirements"])
        self.assertIn("corp.shadowknight.playbook.prep-before-code", payload["active_playbooks"])
        profile_stop_conditions = payload["stop_condition_sources"]["profiles"][0]
        self.assertEqual(profile_stop_conditions["profile"], "runner")
        self.assertEqual(profile_stop_conditions["stop_conditions"], ["secrets_detected"])
        self.assertIn("secrets_detected", payload["stop_conditions"])

    def test_context_rejects_multiple_consumer_views(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                ["context", "--workspace", str(self.internal_repo), "--for-harness", "--for-workflow-engine", "--json"]
            )
        self.assertEqual(exit_code, 2)
        self.assertIn("choose only one consumer view", stderr.getvalue())

    def test_context_for_workflow_engine_exposes_flows_contracts_and_profile_selection(self) -> None:
        write(
            self.corp_repo / "org" / "profiles" / "workflow-review.toml",
            """
            id = "workflow-review"
            stop_conditions = ["external_system_unavailable"]

            [activation]
            required = ["corp.shadowknight.completion_gate.workflow-done"]
            enabled = ["corp.shadowknight.playbook.workflow-review"]
            """,
        )
        write(
            self.corp_repo / "org" / "completion_gates" / "workflow-done" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.workflow-done"
            kind = "completion_gate"
            title = "Workflow Done"
            privacy = "repo-safe"
            owner = "platform"
            evidence_required = ["approval_record", "verification_result"]
            """,
        )
        write(self.corp_repo / "org" / "completion_gates" / "workflow-done" / "body.md", "Workflow completion gate.")
        write(
            self.corp_repo / "org" / "playbooks" / "workflow-review" / "item.toml",
            """
            id = "corp.shadowknight.playbook.workflow-review"
            kind = "playbook"
            title = "Workflow Review"
            privacy = "repo-safe"
            owner = "workflow-team"
            inputs = ["pull_request", "policy_context"]
            outputs = ["review_decision", "evidence_package"]
            evidence_required = ["review_decision"]
            stop_conditions = ["missing_policy_context"]
            """,
        )
        write(self.corp_repo / "org" / "playbooks" / "workflow-review" / "body.md", "Review workflow.")
        write(
            self.corp_repo / "org" / "config.toml",
            """
            id = "shadowknight"
            enabled_sources = ["shared-ext"]
            enabled_skills = ["corp.shadowknight.skill.shell-global"]
            baseline_policies = ["corp.shadowknight.policy.no-leaks"]
            allowed_profiles = ["workflow-review"]
            default_profile = "workflow-review"
            recommended_agent_types = ["shell"]
            minimal_enabled_skills = ["corp.shadowknight.skill.shell-global"]
            protected_fields = ["baseline_policies", "privacy_rules"]
            """,
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "context",
                    "--workspace",
                    str(self.internal_repo),
                    "--profile",
                    "workflow-review",
                    "--for-workflow-engine",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["kind"], "workflow-engine-context")
        self.assertIn("no workflow execution", payload["runtime_boundary"]["non_goals"])
        self.assertIn("workflow graph", payload["runtime_boundary"]["workflow_engine_provides"])
        self.assertEqual(payload["workspace"]["profile"], "workflow-review")
        completion_gate = payload["active_completion_gates"]["corp.shadowknight.completion_gate.workflow-done"]
        self.assertEqual(completion_gate["owner"], "platform")
        self.assertEqual(completion_gate["evidence_required"], ["approval_record", "verification_result"])
        playbook = payload["playbooks"]["corp.shadowknight.playbook.workflow-review"]
        self.assertEqual(playbook["owner"], "workflow-team")
        self.assertEqual(playbook["inputs"], ["pull_request", "policy_context"])
        self.assertEqual(playbook["outputs"], ["review_decision", "evidence_package"])
        self.assertIn("missing_policy_context", payload["stop_conditions"])
        self.assertIn("external_system_unavailable", payload["stop_conditions"])
        self.assertIn("corp.shadowknight.playbook.workflow-review", payload["evidence_requirements"])

    def test_validate_json_reports_governance_status_for_ci(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["validate", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["kind"], "governance-validation")
        self.assertEqual(payload["schema_version"], "v1")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["resolution"]["matched_repo_id"], "internal-app")
        self.assertIn("doctor_summary", payload)
        self.assertIn("warnings", payload)

    def test_validate_strict_fails_on_governance_warnings(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["validate", "--workspace", str(self.internal_repo), "--json", "--strict"])
        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "fail")
        self.assertTrue(payload["strict_failure"])
        self.assertGreater(len(payload["warnings"]), 0)

    def test_validate_returns_nonzero_on_schema_violation(self) -> None:
        self.configure_machine()
        write(
            self.corp_repo / "org" / "skills" / "bad-script" / "item.toml",
            """
            id = "corp.shadowknight.skill.bad-script"
            kind = "skill"
            title = "Bad Script"
            privacy = "repo-safe"
            allows_scripts = true
            """,
        )
        write(self.corp_repo / "org" / "skills" / "bad-script" / "body.md", "Bad body.")
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["validate", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "fail")
        self.assertIn("allows_scripts", payload["errors"][0]["detail"])

    def test_audit_and_doctor_strict_fail_on_governance_warnings(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            audit_exit = main(["audit", "--workspace", str(self.internal_repo), "--json", "--strict"])
        self.assertEqual(audit_exit, 1)
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            doctor_exit = main(["doctor", "--workspace", str(self.internal_repo), "--json", "--strict"])
        self.assertEqual(doctor_exit, 1)

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

    def test_audit_json_explains_activation_targets_recommendations_and_conflicts(self) -> None:
        write(
            self.user_layer / "config.toml",
            """
            id = "local"
            enabled_skills = ["user.local.skill.personal-shell"]
            recommended_skills = ["user.local.skill.suggested-helper"]
            """,
        )
        write(
            self.user_layer / "skills" / "suggested-helper" / "item.toml",
            """
            id = "user.local.skill.suggested-helper"
            kind = "skill"
            title = "Suggested Helper"
            privacy = "repo-safe"
            """,
        )
        write(self.user_layer / "skills" / "suggested-helper" / "body.md", "Suggested helper body")
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["audit", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        shell = report["active_items"]["corp.shadowknight.skill.shell-global"]
        self.assertEqual(shell["activation_reason"], "enabled")
        self.assertEqual(shell["activation_state"], "enabled")
        self.assertFalse(shell["required"])
        self.assertEqual(shell["activation_source"], "enabled")
        self.assertEqual(shell["activated_by"], ["org:shadowknight"])
        self.assertEqual(shell["selected_by_packs"], [])
        self.assertEqual(shell["selected_by_profiles"], [])
        self.assertIn("source_path", shell)
        self.assertEqual(shell["target_outputs"], ["claude", "codex", "cursor"])
        self.assertEqual(shell["privacy_status"], "repo-safe")
        no_leaks = report["active_items"]["corp.shadowknight.policy.no-leaks"]
        self.assertEqual(no_leaks["activation_reason"], "required")
        self.assertTrue(no_leaks["required"])
        ext_review = report["active_items"]["external.shared.skill.ext-review"]
        self.assertEqual(ext_review["status"], "replaced")
        self.assertIsNotNone(ext_review["replaced_from"])
        ext_lint = report["active_items"]["external.shared.skill.ext-lint"]
        self.assertEqual(ext_lint["source_type"], "external")
        self.assertEqual(ext_lint["trust_level"], "unreviewed")
        self.assertFalse(ext_lint["allows_scripts"])
        self.assertIn("standards_registry", report)
        self.assertIn("sprawl_warnings", report)
        self.assertIn("user.local.skill.suggested-helper", report["inactive_recommended_items"])

    def test_registry_json_lists_available_standards_with_filters(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["registry", "--kind", "skill", "--repo-id", "internal-app", "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["filters"]["kind"], "skill")
        self.assertEqual(report["filters"]["repo_id"], "internal-app")
        ids = {item["id"] for item in report["items"]}
        self.assertIn("corp.shadowknight.skill.shell-global", ids)
        self.assertIn("corp.shadowknight.skill.platform-shared", ids)
        self.assertIn("corp.shadowknight.skill.internal-ops", ids)
        self.assertIn("user.local.skill.personal-shell", ids)
        shell = next(item for item in report["items"] if item["id"] == "corp.shadowknight.skill.shell-global")
        self.assertEqual(shell["kind"], "skill")
        self.assertEqual(shell["status"], "active")
        self.assertEqual(shell["review_status"], "unreviewed")
        self.assertEqual(shell["source_type"], "corp")
        self.assertIn("trust_level", shell)

    def test_registry_can_filter_profiles_and_status(self) -> None:
        write(
            self.corp_repo / "org" / "profiles" / "maintainer.toml",
            """
            id = "maintainer"
            owner = "platform-enablement"
            status = "active"
            review_status = "approved"
            intended_consumers = ["human", "harness"]
            context_quality_max_active_items = 12
            """,
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["registry", "--kind", "profile", "--profile", "maintainer", "--status", "active", "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["counts"]["total"], 1)
        profile = report["items"][0]
        self.assertEqual(profile["id"], "maintainer")
        self.assertEqual(profile["kind"], "profile")
        self.assertEqual(profile["review_status"], "approved")
        self.assertEqual(profile["intended_consumers"], ["human", "harness"])
        self.assertEqual(profile["context_quality_max_active_items"], 12)

    def test_audit_sprawl_warnings_cover_duplicate_pack_activation_and_deprecated_active_items(self) -> None:
        write(
            self.corp_repo / "org" / "config.toml",
            """
            id = "shadowknight"
            enabled_sources = ["shared-ext"]
            enabled_skills = ["corp.shadowknight.skill.shell-global"]
            baseline_policies = ["corp.shadowknight.policy.no-leaks"]
            enabled_packs = [
              "corp.shadowknight.pack.review-a",
              "corp.shadowknight.pack.review-b"
            ]
            recommended_agent_types = ["shell"]
            minimal_enabled_skills = ["corp.shadowknight.skill.shell-global"]
            protected_fields = ["baseline_policies", "privacy_rules"]
            """,
        )
        write(
            self.corp_repo / "org" / "skills" / "shell-global" / "item.toml",
            """
            id = "corp.shadowknight.skill.shell-global"
            kind = "skill"
            title = "Shell Global"
            privacy = "repo-safe"
            status = "deprecated"
            owner = "platform-enablement"
            maintainer = "platform-enablement"
            """,
        )
        for slug in ["review-a", "review-b"]:
            write(
                self.corp_repo / "org" / "packs" / slug / "item.toml",
                f"""
                id = "corp.shadowknight.pack.{slug}"
                kind = "pack"
                title = "Review {slug[-1].upper()}"
                privacy = "repo-safe"
                owner = "platform-enablement"
                maintainer = "platform-enablement"

                [activation]
                enabled = ["corp.shadowknight.skill.shell-global"]
                """,
            )
            write(self.corp_repo / "org" / "packs" / slug / "body.md", f"Review pack {slug}")
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["audit", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        self.assertIn(
            "deprecated active item: corp.shadowknight.skill.shell-global",
            report["sprawl_warnings"],
        )
        self.assertIn(
            "multiple packs activate corp.shadowknight.skill.shell-global: corp.shadowknight.pack.review-a, corp.shadowknight.pack.review-b",
            report["sprawl_warnings"],
        )

    def test_sync_internal_repo_writes_outputs_and_updates_agents(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        written = write_sync_output(result)
        self.assertTrue(any(path.name == "resolution.json" for path in written))
        self.assertTrue(any(path.name == "artifacts.json" for path in written))
        agents_md = (self.internal_repo / "AGENTS.md").read_text(encoding="utf-8")
        claude_md = (self.internal_repo / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("<!-- team-agents:start -->", agents_md)
        self.assertIn("# Project Agent Guidance", agents_md)
        self.assertIn("Generated context lives under `.agents/`.", agents_md)
        self.assertIn("## Required Completion Gates", agents_md)
        self.assertIn("Active profile/job", agents_md)
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
        manifest = json.loads((self.internal_repo / ".agents" / "artifacts.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "v1")
        self.assertEqual(manifest["repo_class"], "internal")
        manifest_paths = {entry["path"]: entry for entry in manifest["artifacts"]}
        self.assertIn(".agents/index.md", manifest_paths)
        self.assertIn(".agents/resolution.json", manifest_paths)
        self.assertIn(".agents/artifacts.json", manifest_paths)
        self.assertIn("AGENTS.md", manifest_paths)
        self.assertIn("CLAUDE.md", manifest_paths)
        self.assertIn(".cursor/rules/team-agents.mdc", manifest_paths)
        self.assertEqual(manifest_paths["AGENTS.md"]["kind"], "tool-router")
        self.assertEqual(manifest_paths["AGENTS.md"]["target"], "codex")
        self.assertTrue(manifest_paths["AGENTS.md"]["safe_to_commit"])
        self.assertFalse(manifest_paths["CLAUDE.md"]["safe_to_commit"])
        self.assertFalse(manifest_paths[".cursor/rules/team-agents.mdc"]["safe_to_commit"])
        self.assertFalse(manifest_paths[".agents/resolution.json"]["safe_to_commit"])
        self.assertEqual(
            manifest_paths[".agents/resolution.json"]["source_resolution_hash"],
            manifest["source_resolution_hash"],
        )

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
        user = load_user_layer(machine.user_layer_path)
        resolution = resolve_workspace(self.unknown_repo, machine, corp, user)
        self.assertEqual(resolution.workspace_context.matched_repo_id, "internal-app")
        config = (machine.user_layer_path / "config.toml").read_text(encoding="utf-8")
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
        user = load_user_layer(machine.user_layer_path)
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
        user = load_user_layer(machine.user_layer_path)
        resolution = resolve_workspace(self.unknown_repo, machine, corp, user)
        self.assertTrue(resolution.workspace_context.is_unknown)
        self.assertTrue((self.unknown_repo / ".agents" / "resolution.json").exists())

    def test_attach_unresolved_repo_defaults_to_baseline_on_eof(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with patch("builtins.input", side_effect=EOFError):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["attach", "--workspace", str(self.unknown_repo)])
        self.assertEqual(exit_code, 0)
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
        user = load_user_layer(machine.user_layer_path)
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
        user = load_user_layer(machine.user_layer_path)
        with self.assertRaises(ResolutionError):
            resolve_workspace(self.client_private_repo, machine, corp, user)

    def test_sync_client_repo_fails_on_tracked_agents_conflict(self) -> None:
        self.configure_machine()
        exit_code = main(["sync", "--workspace", str(self.client_tracked_repo)])
        self.assertEqual(exit_code, 1)

    def test_unknown_git_repo_gets_minimal_baseline_and_user_skill(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.unknown_repo, machine, corp, user)
        self.assertIsNone(result.workspace_context.matched_repo_id)
        self.assertEqual(
            set(result.enabled_skills),
            {"corp.shadowknight.skill.shell-global", "user.local.skill.personal-shell"},
        )
        self.assertNotIn("corp.shadowknight.context.platform-map", result.active_contexts)

    def test_non_git_workspace_binding_applies_repo_group_context(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.bound_workspace, machine, corp, user)
        self.assertEqual(result.workspace_context.matched_repo_group_id, "platform")
        self.assertIn("corp.shadowknight.skill.platform-shared", result.enabled_skills)
        self.assertIn("corp.shadowknight.context.platform-map", result.active_contexts)

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

    def test_user_layer_cannot_disable_baseline_policy(self) -> None:
        write(
            self.user_layer / "config.toml",
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
                "--user-path",
                str(self.user_layer),
                "--cache-root",
                str(self.cache_root),
            ]
        )
        self.assertEqual(exit_code, 1)

    def test_resolution_json_records_activation_provenance_across_layers(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        payload = resolve_workspace(self.internal_repo, machine, corp, user).to_dict()
        self.assertEqual(payload["items"]["corp.shadowknight.skill.shell-global"]["activated_by"], ["org:shadowknight"])
        self.assertEqual(payload["items"]["corp.shadowknight.skill.platform-shared"]["activated_by"], ["repo-group:platform"])
        self.assertEqual(payload["items"]["user.local.skill.personal-shell"]["activated_by"], ["user:local"])
        self.assertEqual(payload["items"]["corp.shadowknight.policy.no-leaks"]["activated_by"], ["org:shadowknight"])

    def test_local_user_layer_resolves_contracts_flows_packs_and_profiles(self) -> None:
        write(
            self.user_layer / "config.toml",
            """
            id = "local"
            enabled_skills = ["user.local.skill.personal-shell"]
            optional_completion_gates = ["user.local.completion_gate.personal-quality"]

            [packs]
            enabled = ["user.local.pack.personal-review"]

            [playbooks]
            enabled = ["user.local.playbook.preflight"]

            [profiles]
            enabled = ["user.local.profile.shell"]
            """,
        )
        for folder, kind, slug, title in [
            ("completion_gates", "completion_gate", "personal-quality", "Personal Quality"),
            ("packs", "pack", "personal-review", "Personal Review"),
            ("packs", "pack", "inactive-pack", "Inactive Pack"),
            ("playbooks", "playbook", "preflight", "Preflight"),
            ("profiles", "profile", "shell", "Shell Profile"),
        ]:
            write(
                self.user_layer / folder / slug / "item.toml",
                f"""
                id = "user.local.{kind}.{slug}"
                kind = "{kind}"
                title = "{title}"
                privacy = "repo-safe"
                """,
            )
            write(self.user_layer / folder / slug / "body.md", f"{title} body")
        write(
            self.user_layer / "playbooks" / "preflight" / "item.toml",
            """
            id = "user.local.playbook.preflight"
            kind = "playbook"
            title = "Preflight"
            privacy = "repo-safe"
            owner = "developer-experience"
            inputs = ["issue", "repo_context"]
            outputs = ["patch", "verification_report"]
            evidence_required = ["tests_run", "risk_notes"]
            stop_conditions = ["ambiguous_requirement", "security_boundary_unclear"]
            """,
        )

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        self.assertIn("user.local.completion_gate.personal-quality", result.active_completion_gates)
        self.assertIn("user.local.pack.personal-review", result.active_packs)
        self.assertIn("user.local.playbook.preflight", result.active_playbooks)
        self.assertIn("user.local.profile.shell", result.active_profiles)
        self.assertNotIn("user.local.pack.inactive-pack", result.items)
        payload = result.to_dict()
        self.assertEqual(payload["items"]["user.local.completion_gate.personal-quality"]["activated_by"], ["user:local"])
        self.assertEqual(payload["items"]["user.local.pack.personal-review"]["kind"], "pack")
        playbook = payload["items"]["user.local.playbook.preflight"]
        self.assertEqual(playbook["inputs"], ["issue", "repo_context"])
        self.assertEqual(playbook["outputs"], ["patch", "verification_report"])
        self.assertEqual(playbook["evidence_required"], ["tests_run", "risk_notes"])
        self.assertEqual(playbook["stop_conditions"], ["ambiguous_requirement", "security_boundary_unclear"])

        write_sync_output(result)
        index = (self.internal_repo / ".agents" / "index.md").read_text(encoding="utf-8")
        self.assertIn("- `user.local.playbook.preflight`", index)
        self.assertIn("Inputs: `issue`, `repo_context`", index)
        self.assertIn("Outputs: `patch`, `verification_report`", index)
        self.assertIn("Evidence required: `tests_run`, `risk_notes`", index)
        self.assertIn("Stop conditions: `ambiguous_requirement`, `security_boundary_unclear`", index)

    def test_pack_contents_activate_referenced_items_with_provenance(self) -> None:
        org_config = self.corp_repo / "org" / "config.toml"
        org_config.write_text(
            org_config.read_text(encoding="utf-8")
            + 'enabled_packs = ["corp.shadowknight.pack.review-baseline"]\n',
            encoding="utf-8",
        )
        for folder, kind, slug, title in [
            ("completion_gates", "completion_gate", "pack-done", "Pack Done"),
            ("contexts", "context", "pack-guide", "Pack Guide"),
            ("skills", "skill", "pack-helper", "Pack Helper"),
        ]:
            write(
                self.corp_repo / "org" / folder / slug / "item.toml",
                f"""
                id = "corp.shadowknight.{kind}.{slug}"
                kind = "{kind}"
                title = "{title}"
                privacy = "repo-safe"
                """,
            )
            write(self.corp_repo / "org" / folder / slug / "body.md", f"{title} body")
        write(
            self.corp_repo / "org" / "packs" / "review-baseline" / "item.toml",
            """
            id = "corp.shadowknight.pack.review-baseline"
            kind = "pack"
            title = "Review Baseline"
            privacy = "repo-safe"

            [activation]
            required = ["corp.shadowknight.completion_gate.pack-done"]
            enabled = [
              "corp.shadowknight.context.pack-guide",
              "corp.shadowknight.pack.review-tools"
            ]
            """,
        )
        write(self.corp_repo / "org" / "packs" / "review-baseline" / "body.md", "Review baseline")
        write(
            self.corp_repo / "org" / "packs" / "review-tools" / "item.toml",
            """
            id = "corp.shadowknight.pack.review-tools"
            kind = "pack"
            title = "Review Tools"
            privacy = "repo-safe"

            [activation]
            enabled = ["corp.shadowknight.skill.pack-helper"]
            """,
        )
        write(self.corp_repo / "org" / "packs" / "review-tools" / "body.md", "Review tools")

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        self.assertIn("corp.shadowknight.pack.review-baseline", result.active_packs)
        self.assertIn("corp.shadowknight.pack.review-tools", result.active_packs)
        self.assertIn("corp.shadowknight.completion_gate.pack-done", result.active_completion_gates)
        self.assertIn("corp.shadowknight.context.pack-guide", result.active_contexts)
        self.assertIn("corp.shadowknight.skill.pack-helper", result.enabled_skills)
        self.assertEqual(result.items["corp.shadowknight.completion_gate.pack-done"].activation_reason, "required")
        self.assertEqual(result.items["corp.shadowknight.context.pack-guide"].activation_reason, "enabled")
        self.assertEqual(
            result.items["corp.shadowknight.completion_gate.pack-done"].activated_by,
            ["org:shadowknight", "pack:corp.shadowknight.pack.review-baseline"],
        )
        self.assertEqual(
            result.items["corp.shadowknight.skill.pack-helper"].activated_by,
            [
                "org:shadowknight",
                "pack:corp.shadowknight.pack.review-baseline",
                "pack:corp.shadowknight.pack.review-tools",
            ],
        )
        payload = result.to_dict()
        pack_helper = payload["items"]["corp.shadowknight.skill.pack-helper"]
        self.assertEqual(
            pack_helper["selected_by_packs"],
            ["corp.shadowknight.pack.review-baseline", "corp.shadowknight.pack.review-tools"],
        )
        self.assertEqual(pack_helper["selected_by_profiles"], [])
        self.assertEqual(pack_helper["activation_state"], "enabled")
        self.assertEqual(pack_helper["target_outputs"], ["claude", "codex", "cursor"])

    def test_repo_bootstrap_contract_activates_from_repo_and_renders_guidance(self) -> None:
        repo_config = self.corp_repo / "repos" / "internal-app" / "config.toml"
        repo_config.write_text(
            repo_config.read_text(encoding="utf-8").replace(
                "\n        [[item_override]]",
                '\n        required_completion_gates = ["corp.shadowknight.completion_gate.repo-bootstrap"]\n\n        [[item_override]]',
            ),
            encoding="utf-8",
        )
        write(
            self.corp_repo / "repos" / "internal-app" / "completion_gates" / "repo-bootstrap" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.repo-bootstrap"
            kind = "completion_gate"
            title = "Repo Bootstrap"
            privacy = "repo-safe"
            tags = ["bootstrap", "minimal-verification"]
            """,
        )
        write(
            self.corp_repo / "repos" / "internal-app" / "completion_gates" / "repo-bootstrap" / "body.md",
            """
            # Repo Bootstrap

            Last verified: 2026-05-21

            ## Commands

            ```bash
            python -m pip install -e .
            PYTHONPATH=src python -m unittest discover -s tests -v
            ```

            ## Minimal verification

            Run the unittest command above before handing off changes.
            """,
        )

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        self.assertIn("corp.shadowknight.completion_gate.repo-bootstrap", result.active_completion_gates)
        self.assertEqual(result.items["corp.shadowknight.completion_gate.repo-bootstrap"].activated_by, ["repo:internal-app"])

        write_sync_output(result)
        bootstrap = (self.internal_repo / ".agents" / "bootstrap.md").read_text(encoding="utf-8")
        index = (self.internal_repo / ".agents" / "index.md").read_text(encoding="utf-8")
        self.assertIn("Repo Bootstrap Guidance", index)
        self.assertIn("python -m pip install -e .", bootstrap)
        self.assertIn("PYTHONPATH=src python -m unittest discover -s tests -v", bootstrap)

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        bootstrap_check = next(check for check in report["checks"] if check["name"] == "bootstrap-guidance")
        self.assertEqual(bootstrap_check["status"], "ok")

    def test_bootstrap_contract_can_be_activated_by_profile(self) -> None:
        write(
            self.corp_repo / "org" / "profiles" / "coder.toml",
            """
            id = "coder"
            title = "Coder"

            [activation]
            required = ["corp.shadowknight.completion_gate.repo-bootstrap"]
            """,
        )
        write(
            self.corp_repo / "org" / "completion_gates" / "repo-bootstrap" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.repo-bootstrap"
            kind = "completion_gate"
            title = "Repo Bootstrap"
            privacy = "repo-safe"
            tags = ["bootstrap"]
            """,
        )
        write(self.corp_repo / "org" / "completion_gates" / "repo-bootstrap" / "body.md", "Minimal verification: run tests.")

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user, profile="coder")

        self.assertIn("corp.shadowknight.completion_gate.repo-bootstrap", result.active_completion_gates)
        self.assertEqual(result.items["corp.shadowknight.completion_gate.repo-bootstrap"].activated_by, ["profile:coder"])

    def test_circular_pack_references_are_rejected(self) -> None:
        write(
            self.user_layer / "config.toml",
            """
            id = "local"

            [packs]
            enabled = ["user.local.pack.alpha"]
            """,
        )
        for slug, next_slug in [("alpha", "beta"), ("beta", "alpha")]:
            write(
                self.user_layer / "packs" / slug / "item.toml",
                f"""
                id = "user.local.pack.{slug}"
                kind = "pack"
                title = "{slug.title()}"
                privacy = "repo-safe"

                [activation]
                enabled = ["user.local.pack.{next_slug}"]
                """,
            )
            write(self.user_layer / "packs" / slug / "body.md", f"{slug} body")

        machine = MachineConfig(
            corp_repo_path=self.corp_repo,
            user_layer_path=self.user_layer,
            cache_root=self.cache_root,
            default_tool_target="all",
        )
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        with self.assertRaisesRegex(ResolutionError, "Circular pack reference"):
            resolve_workspace(self.internal_repo, machine, corp, user)

    def test_activation_is_opt_in_with_required_and_recommended_distinct(self) -> None:
        org_config = self.corp_repo / "org" / "config.toml"
        org_config.write_text(
            org_config.read_text(encoding="utf-8")
            + 'required_packs = ["corp.shadowknight.pack.client-safe"]\n',
            encoding="utf-8",
        )
        write(
            self.corp_repo / "org" / "packs" / "client-safe" / "item.toml",
            """
            id = "corp.shadowknight.pack.client-safe"
            kind = "pack"
            title = "Client Safe"
            privacy = "repo-safe"
            """,
        )
        write(self.corp_repo / "org" / "packs" / "client-safe" / "body.md", "Client safe pack")
        write(
            self.user_layer / "config.toml",
            """
            id = "local"

            [skills]
            enabled = ["user.local.skill.personal-shell"]
            recommended = ["user.local.skill.recommended-helper"]

            [packs]
            recommended = ["user.local.pack.recommended-pack"]
            """,
        )
        for folder, kind, slug, title in [
            ("skills", "skill", "recommended-helper", "Recommended Helper"),
            ("skills", "skill", "inactive-helper", "Inactive Helper"),
            ("packs", "pack", "recommended-pack", "Recommended Pack"),
            ("packs", "pack", "inactive-pack", "Inactive Pack"),
        ]:
            write(
                self.user_layer / folder / slug / "item.toml",
                f"""
                id = "user.local.{kind}.{slug}"
                kind = "{kind}"
                title = "{title}"
                privacy = "repo-safe"
                """,
            )
            write(self.user_layer / folder / slug / "body.md", f"{title} body")

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        self.assertIn("corp.shadowknight.pack.client-safe", result.active_packs)
        self.assertEqual(result.items["corp.shadowknight.pack.client-safe"].activation_reason, "required")
        self.assertEqual(result.items["user.local.skill.personal-shell"].activation_reason, "enabled")
        self.assertNotIn("user.local.skill.inactive-helper", result.items)
        self.assertNotIn("user.local.pack.inactive-pack", result.items)
        self.assertIn("user.local.skill.recommended-helper", result.recommended_items)
        self.assertIn("user.local.pack.recommended-pack", result.recommended_items)
        self.assertNotIn("user.local.skill.recommended-helper", result.items)
        self.assertNotIn("user.local.pack.recommended-pack", result.items)

    def test_generalized_activation_table_activates_items(self) -> None:
        write(
            self.user_layer / "config.toml",
            """
            id = "local"

            [activation]
            required = ["user.local.completion_gate.personal-done"]
            enabled = [
              "user.local.skill.personal-shell",
              "user.local.context.personal-notes",
              "user.local.playbook.personal-playbook"
            ]
            recommended = ["user.local.pack.suggested-pack"]
            """,
        )
        for folder, kind, slug, title in [
            ("completion_gates", "completion_gate", "personal-done", "Personal Done"),
            ("contexts", "context", "personal-notes", "Personal Notes"),
            ("playbooks", "playbook", "personal-playbook", "Personal Playbook"),
            ("packs", "pack", "suggested-pack", "Suggested Pack"),
        ]:
            write(
                self.user_layer / folder / slug / "item.toml",
                f"""
                id = "user.local.{kind}.{slug}"
                kind = "{kind}"
                title = "{title}"
                privacy = "repo-safe"
                """,
            )
            write(self.user_layer / folder / slug / "body.md", f"{title} body")

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        self.assertIn("user.local.skill.personal-shell", result.enabled_skills)
        self.assertIn("user.local.context.personal-notes", result.active_contexts)
        self.assertIn("user.local.playbook.personal-playbook", result.active_playbooks)
        self.assertIn("user.local.completion_gate.personal-done", result.active_completion_gates)
        self.assertEqual(result.items["user.local.completion_gate.personal-done"].activation_reason, "required")
        self.assertIn("user.local.pack.suggested-pack", result.recommended_items)
        self.assertNotIn("user.local.pack.suggested-pack", result.items)

    def test_generalized_activation_table_works_in_profiles(self) -> None:
        write(
            self.corp_repo / "org" / "profiles" / "reviewer.toml",
            """
            id = "reviewer"

            [activation]
            enabled = ["corp.shadowknight.skill.repo-onboarding"]
            required = ["corp.shadowknight.completion_gate.review-done"]
            """,
        )
        write(
            self.corp_repo / "org" / "completion_gates" / "review-done" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.review-done"
            kind = "completion_gate"
            title = "Review Done"
            privacy = "repo-safe"
            """,
        )
        write(self.corp_repo / "org" / "completion_gates" / "review-done" / "body.md", "Review done")
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user, profile="reviewer")
        self.assertIn("corp.shadowknight.skill.repo-onboarding", result.enabled_skills)
        self.assertIn("corp.shadowknight.completion_gate.review-done", result.active_completion_gates)
        self.assertEqual(result.items["corp.shadowknight.completion_gate.review-done"].activated_by, ["profile:reviewer"])

    def test_resolution_warns_about_compatibility_mismatches(self) -> None:
        org_config = self.corp_repo / "org" / "config.toml"
        org_config.write_text(
            org_config.read_text(encoding="utf-8")
            + """
            languages = ["python"]
            frameworks = ["django"]
            framework_versions = { django = "3.2" }
            repo_tags = ["web-api"]
            """,
            encoding="utf-8",
        )
        shell_item = self.corp_repo / "org" / "skills" / "shell-global" / "item.toml"
        shell_item.write_text(
            shell_item.read_text(encoding="utf-8")
            + """
            applies_to_languages = ["ruby"]
            applies_to_frameworks = ["rails"]
            compatible_versions = { django = ">=4.2,<6" }
            repo_tags = ["cli"]
            """,
            encoding="utf-8",
        )

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)

        self.assertIn("corp.shadowknight.skill.shell-global", result.enabled_skills)
        warnings = "\n".join(result.warnings)
        self.assertIn("applies_to_languages", warnings)
        self.assertIn("applies_to_frameworks", warnings)
        self.assertIn("django version 3.2 does not satisfy >=4.2,<6", warnings)
        self.assertIn("repo_tags", warnings)
        payload = result.to_dict()
        shell = payload["items"]["corp.shadowknight.skill.shell-global"]
        self.assertEqual(shell["applies_to_languages"], ["ruby"])
        self.assertEqual(shell["compatible_versions"], {"django": ">=4.2,<6"})

    def test_profiles_select_different_context_sets(self) -> None:
        org_config = self.corp_repo / "org" / "config.toml"
        org_config.write_text(
            org_config.read_text(encoding="utf-8")
            + 'allowed_profiles = ["coder", "reviewer"]\n'
            + 'default_profile = "coder"\n',
            encoding="utf-8",
        )
        for slug, title in [("coder-playbook", "Coder Playbook"), ("reviewer-playbook", "Reviewer Playbook")]:
            write(
                self.corp_repo / "org" / "playbooks" / slug / "item.toml",
                f"""
                id = "corp.shadowknight.playbook.{slug}"
                kind = "playbook"
                title = "{title}"
                privacy = "repo-safe"
                """,
            )
            write(self.corp_repo / "org" / "playbooks" / slug / "body.md", f"{title} body")
        write(
            self.corp_repo / "org" / "completion_gates" / "review-done" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.review-done"
            kind = "completion_gate"
            title = "Review Done"
            privacy = "repo-safe"
            """,
        )
        write(self.corp_repo / "org" / "completion_gates" / "review-done" / "body.md", "Review done completion gate")
        write(
            self.corp_repo / "org" / "profiles" / "coder.toml",
            """
            id = "coder"
            enabled_playbooks = ["corp.shadowknight.playbook.coder-playbook"]
            contexts = ["corp.shadowknight.context.platform-map"]
            """,
        )
        write(
            self.corp_repo / "org" / "profiles" / "reviewer.toml",
            """
            id = "reviewer"
            enabled_playbooks = ["corp.shadowknight.playbook.reviewer-playbook"]
            required_completion_gates = ["corp.shadowknight.completion_gate.review-done"]
            enabled_skills = ["corp.shadowknight.skill.repo-onboarding"]
            """,
        )

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        default_result = resolve_workspace(self.internal_repo, machine, corp, user)
        reviewer_result = resolve_workspace(self.internal_repo, machine, corp, user, profile="reviewer")
        self.assertEqual(default_result.workspace_context.profile, "coder")
        self.assertIn("corp.shadowknight.playbook.coder-playbook", default_result.active_playbooks)
        self.assertNotIn("corp.shadowknight.playbook.reviewer-playbook", default_result.items)
        self.assertEqual(reviewer_result.workspace_context.profile, "reviewer")
        self.assertIn("corp.shadowknight.playbook.reviewer-playbook", reviewer_result.active_playbooks)
        self.assertIn("corp.shadowknight.completion_gate.review-done", reviewer_result.active_completion_gates)
        self.assertIn("corp.shadowknight.skill.repo-onboarding", reviewer_result.enabled_skills)
        self.assertEqual(reviewer_result.layer_chain, ["org", "repo-group", "repo", "profile", "user"])
        self.assertEqual(
            reviewer_result.items["corp.shadowknight.completion_gate.review-done"].activated_by,
            ["profile:reviewer"],
        )
        self.assertEqual(
            reviewer_result.to_dict()["items"]["corp.shadowknight.completion_gate.review-done"]["selected_by_profiles"],
            ["reviewer"],
        )

    def test_user_profile_additions_do_not_shadow_corp_profile_requirements(self) -> None:
        org_config = self.corp_repo / "org" / "config.toml"
        org_config.write_text(
            org_config.read_text(encoding="utf-8") + 'allowed_profiles = ["reviewer"]\n',
            encoding="utf-8",
        )
        write(
            self.corp_repo / "org" / "completion_gates" / "review-done" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.review-done"
            kind = "completion_gate"
            title = "Review Done"
            privacy = "repo-safe"
            """,
        )
        write(self.corp_repo / "org" / "completion_gates" / "review-done" / "body.md", "Review done completion gate")
        write(
            self.corp_repo / "org" / "profiles" / "reviewer.toml",
            """
            id = "reviewer"

            [activation]
            required = ["corp.shadowknight.completion_gate.review-done"]
            """,
        )
        write(
            self.user_layer / "profiles" / "reviewer.toml",
            """
            id = "reviewer"

            [activation]
            enabled = ["user.local.skill.personal-shell"]
            """,
        )

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user, profile="reviewer")
        self.assertIn("corp.shadowknight.completion_gate.review-done", result.active_completion_gates)
        self.assertIn("user.local.skill.personal-shell", result.enabled_skills)
        self.assertEqual(result.layer_chain, ["org", "repo-group", "repo", "profile", "profile", "user"])

    def test_user_layer_cannot_weaken_corp_private_item(self) -> None:
        write(
            self.user_layer / "skills" / "internal-ops-replacement" / "item.toml",
            """
            id = "corp.shadowknight.skill.internal-ops"
            kind = "skill"
            title = "Weakened Internal Ops"
            privacy = "repo-safe"
            """,
        )
        write(
            self.user_layer / "skills" / "internal-ops-replacement" / "body.md",
            "attempted weaker replacement",
        )
        write(
            self.user_layer / "config.toml",
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
                "--user-path",
                str(self.user_layer),
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
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        with self.assertRaisesRegex(ProtectionError, "Tracked .agents content already exists"):
            write_sync_output(result)

    def test_user_personal_source_is_pinned_and_loaded(self) -> None:
        write(
            self.user_layer / "config.toml",
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
            self.user_layer / "sources" / "personal-remote-source.toml",
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
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.unknown_repo, machine, corp, user)
        self.assertIn("personal-remote-source", result.enabled_sources)
        self.assertIn("user.remote.skill.personal-remote", result.enabled_skills)
        cached_checkout = machine.cache_root / "sources" / "personal-remote-source" / self.personal_commit / "checkout"
        self.assertTrue(cached_checkout.exists())
        library_checkout = self.home / ".team-agents" / "library" / "external" / f"personal-remote-source@{self.personal_commit}"
        self.assertFalse(library_checkout.is_symlink())
        self.assertTrue((library_checkout / "skills" / "personal-remote" / "body.md").exists())
        self.assertEqual(
            (library_checkout / "skills" / "personal-remote" / "body.md").read_text(encoding="utf-8"),
            (cached_checkout / "skills" / "personal-remote" / "body.md").read_text(encoding="utf-8"),
        )
        trust_store = json.loads((machine.cache_root / "trust" / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(trust_store["sources"]["personal-remote-source"]["trust_mode"], "trust-on-first-use")

    def test_multi_remote_ambiguity_fails_explicitly(self) -> None:
        git(self.internal_repo, "remote", "add", "secondary", "https://git.example.test/demo/internal-alt.git")
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
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

    def test_doctor_warns_when_bootstrap_guidance_is_missing(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        bootstrap_check = next(check for check in report["checks"] if check["name"] == "bootstrap-guidance")
        self.assertEqual(bootstrap_check["status"], "warn")
        self.assertIn("no active repo bootstrap", bootstrap_check["detail"])

    def test_doctor_warns_about_unreviewed_active_external_skills(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        trust_check = next(check for check in report["checks"] if check["name"] == "unreviewed-external-skills")
        self.assertEqual(trust_check["status"], "warn")
        self.assertIn("external.shared.skill.ext-lint", trust_check["detail"])

    def test_doctor_warns_when_git_workspace_remote_matches_no_configured_repo(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.unknown_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        match_check = next(check for check in report["checks"] if check["name"] == "workspace-repo-match")
        self.assertEqual(match_check["status"], "warn")
        self.assertIn("git.example.test/demo/unknown", match_check["detail"])
        self.assertIn("closest configured repo", match_check["detail"])

    def test_doctor_warns_about_deprecated_active_items(self) -> None:
        write(
            self.corp_repo / "org" / "skills" / "shell-global" / "item.toml",
            """
            id = "corp.shadowknight.skill.shell-global"
            kind = "skill"
            title = "Shell Global"
            privacy = "repo-safe"
            status = "deprecated"
            deprecated_by = "corp.shadowknight.skill.platform-shared"
            sunset_after = "2026-12-31"
            """,
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        deprecated_check = next(check for check in report["checks"] if check["name"] == "deprecated-active-items")
        self.assertEqual(deprecated_check["status"], "warn")
        self.assertIn("corp.shadowknight.skill.shell-global", deprecated_check["detail"])

    def test_high_risk_intended_consumers_warn_without_safety_metadata(self) -> None:
        write(
            self.corp_repo / "org" / "config.toml",
            """
            id = "shadowknight"
            enabled_sources = ["shared-ext"]
            enabled_skills = ["corp.shadowknight.skill.shell-global"]
            baseline_policies = ["corp.shadowknight.policy.no-leaks"]
            default_profile = "runner"
            recommended_agent_types = ["shell"]
            minimal_enabled_skills = ["corp.shadowknight.skill.shell-global"]
            protected_fields = ["baseline_policies", "privacy_rules"]
            """,
        )
        write(
            self.corp_repo / "org" / "profiles" / "runner.toml",
            """
            id = "runner"
            title = "Runner"
            intended_consumers = ["harness", "workflow-engine"]

            [activation]
            enabled = ["corp.shadowknight.skill.shell-global"]
            """,
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        codes = {warning["code"] for warning in report["consumer_safety_warnings"]}
        self.assertIn("missing-consumer-stop-conditions", codes)

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["context", "--workspace", str(self.internal_repo), "--for-harness", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        context_codes = {warning["code"] for warning in payload["consumer_safety_warnings"]}
        self.assertEqual(codes, context_codes)

    def test_doctor_warns_when_profile_active_item_threshold_is_exceeded(self) -> None:
        org_config = self.corp_repo / "org" / "config.toml"
        org_config.write_text(
            org_config.read_text(encoding="utf-8")
            + 'allowed_profiles = ["lean"]\n'
            + 'default_profile = "lean"\n',
            encoding="utf-8",
        )
        write(
            self.corp_repo / "org" / "profiles" / "lean.toml",
            """
            id = "lean"
            context_quality_max_active_items = 2
            """,
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        warning = next(item for item in report["context_quality_warnings"] if item["code"] == "too-many-active-items")
        self.assertIn("exceeds threshold 2", warning["detail"])
        self.assertIn("context_quality_max_active_items", warning["remediation"])
        check = next(check for check in report["checks"] if check["name"] == "context-quality:too-many-active-items")
        self.assertEqual(check["status"], "warn")

    def test_doctor_warns_when_client_repo_lacks_client_data_boundary(self) -> None:
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.client_tracked_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        warning = next(
            item for item in report["context_quality_warnings"] if item["code"] == "missing-client-data-boundary"
        )
        self.assertIn("client repo", warning["detail"])
        self.assertIn("client data handling", warning["remediation"])

    def test_review_status_and_deprecation_metadata_surface_in_context_and_audit(self) -> None:
        write(
            self.corp_repo / "org" / "skills" / "shell-global" / "item.toml",
            """
            id = "corp.shadowknight.skill.shell-global"
            kind = "skill"
            title = "Shell Global"
            privacy = "repo-safe"
            owner = "platform-enablement"
            maintainer = "agent-standards"
            status = "draft"
            review_status = "reviewed"
            deprecated_by = "corp.shadowknight.skill.platform-shared"
            sunset_after = "2026-12-31"
            """,
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["context", "--workspace", str(self.internal_repo), "--pretty"])
        self.assertEqual(exit_code, 0)
        context = json.loads(stdout.getvalue())
        shell = context["items"]["corp.shadowknight.skill.shell-global"]
        self.assertEqual(shell["lifecycle_status"], "draft")
        self.assertEqual(shell["review_status"], "reviewed")
        self.assertEqual(shell["deprecated_by"], "corp.shadowknight.skill.platform-shared")
        self.assertEqual(shell["sunset_after"], "2026-12-31")

        audit_stdout = StringIO()
        with redirect_stdout(audit_stdout), redirect_stderr(StringIO()):
            exit_code = main(["audit", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        audit = json.loads(audit_stdout.getvalue())
        audit_shell = audit["active_items"]["corp.shadowknight.skill.shell-global"]
        self.assertEqual(audit_shell["review_status"], "reviewed")
        self.assertEqual(audit_shell["owner"], "platform-enablement")

    def test_source_trust_level_marks_external_skills_reviewed(self) -> None:
        manifest = self.corp_repo / "org" / "sources" / "shared-ext.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + '\ntrust_level = "corp-reviewed"\nreviewed_by = "platform-enablement"\nreviewed_at = "2026-05-21"\n',
            encoding="utf-8",
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(stdout.getvalue())
        trust_check = next(check for check in report["checks"] if check["name"] == "unreviewed-external-skills")
        self.assertEqual(trust_check["status"], "ok")
        ext_lint = report["resolution"]["enabled_skills"]
        self.assertIn("external.shared.skill.ext-lint", ext_lint)
        machine = load_machine_config()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        payload = resolve_workspace(self.internal_repo, machine, corp, user).to_dict()
        self.assertEqual(payload["items"]["external.shared.skill.ext-lint"]["trust_level"], "corp-reviewed")

    def test_allows_scripts_true_is_rejected_for_v1_items(self) -> None:
        write(
            self.user_layer / "skills" / "scripted" / "item.toml",
            """
            id = "user.local.skill.scripted"
            kind = "skill"
            title = "Scripted"
            privacy = "repo-safe"
            allows_scripts = true
            """,
        )
        write(self.user_layer / "skills" / "scripted" / "body.md", "Scripted body")
        with self.assertRaisesRegex(ValidationError, "allows_scripts = true is not supported"):
            load_user_layer(self.user_layer)

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
              { rule = "local_user_layer_must_be_git_backed", severity = "warn", remediation = "Put local user layer under git" },
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
        self.assertEqual(entries["local_user_layer_must_be_git_backed"]["severity"], "warn")
        self.assertFalse(entries["local_user_layer_must_be_git_backed"]["compliant"])
        self.assertFalse(entries["required_skill_ids"]["compliant"])
        self.assertIn("missing required skills", entries["required_skill_ids"]["detail"])
        self.assertFalse(entries["forbidden_source_patterns"]["compliant"])
        self.assertIn("remediation", entries["forbidden_source_patterns"])

    def test_doctor_json_reports_completion_gate_compliance(self) -> None:
        write(
            self.corp_repo / "org" / "config.toml",
            """
            id = "shadowknight"
            enabled_sources = ["shared-ext"]
            enabled_skills = ["corp.shadowknight.skill.shell-global"]
            baseline_policies = ["corp.shadowknight.policy.no-leaks"]
            required_completion_gates = ["corp.shadowknight.completion_gate.definition-of-done"]
            recommended_agent_types = ["shell"]
            minimal_enabled_skills = ["corp.shadowknight.skill.shell-global"]
            protected_fields = ["baseline_policies", "privacy_rules"]
            """,
        )
        write(
            self.corp_repo / "org" / "completion_gates" / "definition-of-done" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.definition-of-done"
            kind = "completion_gate"
            title = "Definition Of Done"
            privacy = "repo-safe"
            policy_rules = [
              { rule = "required_completion_gate_ids", severity = "fail", completion_gate_ids = ["corp.shadowknight.completion_gate.missing-evidence"], remediation = "Require the evidence completion gate" }
            ]
            """,
        )
        write(
            self.corp_repo / "org" / "completion_gates" / "definition-of-done" / "body.md",
            "Definition of done completion_gate",
        )
        self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["doctor", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 1)
        report = json.loads(stdout.getvalue())
        self.assertIn("completion_gate_compliance", report)
        self.assertIn("corp.shadowknight.completion_gate.definition-of-done", report["resolution"]["active_completion_gates"])
        entries = {entry["rule"]: entry for entry in report["completion_gate_compliance"]}
        self.assertFalse(entries["required_completion_gate_ids"]["compliant"])
        self.assertIn("missing required completion gates", entries["required_completion_gate_ids"]["detail"])

    def test_contract_evidence_requirements_surface_in_context_and_audit(self) -> None:
        org_config = self.corp_repo / "org" / "config.toml"
        org_config.write_text(
            org_config.read_text(encoding="utf-8")
            + 'required_completion_gates = ["corp.shadowknight.completion_gate.definition-of-done"]\n',
            encoding="utf-8",
        )
        write(
            self.corp_repo / "org" / "completion_gates" / "definition-of-done" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.definition-of-done"
            kind = "completion_gate"
            title = "Definition Of Done"
            privacy = "repo-safe"
            evidence_required = [
              "tests_run",
              "files_changed_summary",
              "risk_notes",
              "verification_command_output"
            ]
            """,
        )
        write(self.corp_repo / "org" / "completion_gates" / "definition-of-done" / "body.md", "Show evidence before done.")

        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        self.assertIn("corp.shadowknight.completion_gate.definition-of-done", result.active_completion_gates)
        self.assertEqual(
            result.to_dict()["items"]["corp.shadowknight.completion_gate.definition-of-done"]["evidence_required"],
            ["tests_run", "files_changed_summary", "risk_notes", "verification_command_output"],
        )

        write_sync_output(result)
        index = (self.internal_repo / ".agents" / "index.md").read_text(encoding="utf-8")
        agents = (self.internal_repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Required Evidence Before Done", index)
        self.assertIn("tests_run", index)
        self.assertIn("Required Evidence Before Done", agents)
        self.assertIn("verification_command_output", agents)

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["audit", "--workspace", str(self.internal_repo), "--json"])
        self.assertEqual(exit_code, 0)
        audit = json.loads(stdout.getvalue())
        self.assertEqual(
            audit["evidence_requirements"]["corp.shadowknight.completion_gate.definition-of-done"],
            ["tests_run", "files_changed_summary", "risk_notes", "verification_command_output"],
        )

    def test_user_layer_cannot_replace_required_contract(self) -> None:
        org_config = self.corp_repo / "org" / "config.toml"
        org_config.write_text(
            org_config.read_text(encoding="utf-8")
            + 'required_completion_gates = ["corp.shadowknight.completion_gate.definition-of-done"]\n',
            encoding="utf-8",
        )
        write(
            self.corp_repo / "org" / "completion_gates" / "definition-of-done" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.definition-of-done"
            kind = "completion_gate"
            title = "Definition Of Done"
            privacy = "repo-safe"
            """,
        )
        write(self.corp_repo / "org" / "completion_gates" / "definition-of-done" / "body.md", "Required completion gate")
        write(
            self.user_layer / "completion_gates" / "definition-of-done" / "item.toml",
            """
            id = "corp.shadowknight.completion_gate.definition-of-done"
            kind = "completion_gate"
            title = "Weakened Definition Of Done"
            privacy = "repo-safe"
            """,
        )
        write(self.user_layer / "completion_gates" / "definition-of-done" / "body.md", "User replacement")
        machine = MachineConfig(
            corp_repo_path=self.corp_repo,
            user_layer_path=self.user_layer,
            cache_root=self.cache_root,
            default_tool_target="all",
        )
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
        with self.assertRaisesRegex(ResolutionError, "may not replace required item"):
            resolve_workspace(self.internal_repo, machine, corp, user)

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
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.client_private_repo, machine, corp, user)
        write_sync_output(result)
        payload = json.loads((self.client_private_repo / ".agents" / "resolution.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.client_private_repo / ".agents" / "artifacts.json").read_text(encoding="utf-8"))
        shell_skill = payload["items"]["corp.shadowknight.skill.shell-global"]
        self.assertIn("body", shell_skill)
        for item in payload["items"].values():
            if item["privacy"] == "corp-private":
                self.assertNotIn("body", item)
        manifest_paths = {entry["path"]: entry for entry in manifest["artifacts"]}
        self.assertFalse(manifest_paths["AGENTS.md"]["safe_to_commit"])
        self.assertFalse(manifest_paths[".agents/index.md"]["safe_to_commit"])
        self.assertEqual(manifest_paths["AGENTS.md"]["target"], "codex")

    def test_internal_tracked_agents_without_markers_gets_managed_block_appended(self) -> None:
        machine = self.configure_machine()
        corp = load_corp_repo(machine.corp_repo_path)
        user = load_user_layer(machine.user_layer_path)
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
        user = load_user_layer(machine.user_layer_path)
        result = resolve_workspace(self.internal_repo, machine, corp, user)
        self.assertEqual(result.source_details["shared-ext"].trust_status, "verified-manifest-fingerprint")

    def test_init_commands_create_scaffolds(self) -> None:
        corp_dest = self.root / "generated-corp"
        user_dest = self.root / "generated-user"
        self.assertEqual(main(["init-corp-repo", "--dest", str(corp_dest)]), 0)
        self.assertEqual(main(["init-user-layer", "--dest", str(user_dest)]), 0)
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
                "--user-path",
                str(user_dest),
                "--cache-root",
                str(self.cache_root),
                "--init-corp-if-missing",
                "--init-user-if-missing",
                "--import-skills-from",
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
                "--user-path",
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
                "--user-path",
                str(user_dest),
                "--cache-root",
                str(self.cache_root),
                "--init-corp-if-missing",
                "--init-user-if-missing",
                "--import-skills-from",
                str(source_root),
                "--import-skills-to",
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
                "--user-path",
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
                "--user-path",
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
        self.assertTrue((machine.user_layer_path / "skills" / "reviewer").exists())

        (source_root / "reviewer" / "SKILL.md").unlink()
        write(source_root / "linter" / "SKILL.md", "# Linter")
        result = main(["refresh-personal-skills", "--source", str(source_root)])
        self.assertEqual(result, 0)
        user_config = (machine.user_layer_path / "config.toml").read_text(encoding="utf-8")
        self.assertFalse((machine.user_layer_path / "skills" / "reviewer").exists())
        self.assertTrue((machine.user_layer_path / "skills" / "linter").exists())
        self.assertNotIn("user.local.skill.reviewer", user_config)
        self.assertIn("user.local.skill.linter", user_config)

    def test_refresh_personal_skills_can_import_without_auto_enabling(self) -> None:
        machine = self.configure_machine()
        source_root = self.root / "codex-skills"
        write(source_root / "reviewer" / "SKILL.md", "# Reviewer")
        result = main(["refresh-personal-skills", "--source", str(source_root), "--no-enable-imported"])
        self.assertEqual(result, 0)

        user_config = (machine.user_layer_path / "config.toml").read_text(encoding="utf-8")
        self.assertTrue((machine.user_layer_path / "skills" / "reviewer").exists())
        self.assertNotIn("user.local.skill.reviewer", user_config)
        self.assertIn("user.local.skill.personal-shell", user_config)

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
                    "--enable-context",
                    "corp.shadowknight.context.platform-map",
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

    def test_configure_org_updates_org_layer_deltas(self) -> None:
        machine = self.configure_machine()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "configure-org",
                    "--enable-skill",
                    "corp.shadowknight.skill.repo-onboarding",
                    "--minimal-enable-skill",
                    "corp.shadowknight.skill.repo-onboarding",
                    "--enable-source",
                    "shared-ext",
                    "--recommended-agent-type",
                    "shell",
                    "--recommended-agent-type",
                    "reviewer",
                    "--no-sync",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["synced"])
        self.assertIn("corp.shadowknight.skill.repo-onboarding", payload["org_layer"]["enabled_skills"])
        self.assertIn("corp.shadowknight.skill.repo-onboarding", payload["org_layer"]["minimal_enabled_skills"])
        self.assertIn("shared-ext", payload["org_layer"]["enabled_sources"])
        self.assertEqual(payload["org_layer"]["recommended_agent_types"], ["shell", "reviewer"])

        org_config = (machine.corp_repo_path / "org" / "config.toml").read_text(encoding="utf-8")
        self.assertIn(
            'enabled_skills = ["corp.shadowknight.skill.shell-global", "corp.shadowknight.skill.repo-onboarding"]',
            org_config,
        )
        self.assertIn(
            'minimal_enabled_skills = ["corp.shadowknight.skill.shell-global", "corp.shadowknight.skill.repo-onboarding"]',
            org_config,
        )
        self.assertIn('enabled_sources = ["shared-ext"]', org_config)
        self.assertIn('recommended_agent_types = ["shell", "reviewer"]', org_config)

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
        user_config = machine.user_layer_path / "config.toml"
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
            "corp.shadowknight.context.platform-map",
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
        self.assertIn("corp.shadowknight.context.platform-map", payload["contexts"])
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
        user = load_user_layer(machine.user_layer_path)
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
        user = load_user_layer(machine.user_layer_path)
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
                "--user-path",
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
                "--user-path",
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
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
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
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["promoted_skill_ids"], ["corp.example-org.skill.reviewer"])
        self.assertIn("missing promotion_checklist", payload["warnings"][0])
        user_config = (user_dest / "config.toml").read_text(encoding="utf-8")
        org_config = (corp_dest / "org" / "config.toml").read_text(encoding="utf-8")
        self.assertNotIn("user.local.skill.reviewer", user_config)
        self.assertIn("corp.example-org.skill.reviewer", org_config)
        self.assertFalse((user_dest / "skills" / "reviewer").exists())
        self.assertTrue((corp_dest / "org" / "skills" / "reviewer").exists())
        body = (corp_dest / "org" / "skills" / "reviewer" / "body.md").read_text(encoding="utf-8")
        self.assertIn("corp.example-org.context.reviewer-notes-md", body)
        doc_item = (corp_dest / "org" / "contexts" / "reviewer-notes-md" / "item.toml").read_text(encoding="utf-8")
        self.assertIn('id = "corp.example-org.context.reviewer-notes-md"', doc_item)

    def test_promote_skills_preserves_promotion_checklist_without_warning(self) -> None:
        self.configure_machine()
        user_config = self.user_layer / "config.toml"
        user_config.write_text(
            user_config.read_text(encoding="utf-8").replace(
                'enabled_skills = ["user.local.skill.personal-shell"]',
                'enabled_skills = ["user.local.skill.personal-shell", "user.local.skill.evidence-backed"]',
            ),
            encoding="utf-8",
        )
        write(
            self.user_layer / "skills" / "evidence-backed" / "item.toml",
            """
            id = "user.local.skill.evidence-backed"
            kind = "skill"
            title = "Evidence Backed"
            privacy = "repo-safe"

            [promotion_checklist]
            task = "Review database migrations"
            applicability = "Python services with Alembic migrations"
            evidence = "Caught missing downgrade paths in sampled PRs"
            risks = "May over-warn for data-only migrations"
            scope = "Migration review only"
            redundancy = "Not covered by existing completion gates"
            """,
        )
        write(self.user_layer / "skills" / "evidence-backed" / "body.md", "Evidence backed body")

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            promote_result = main(
                [
                    "promote-skills",
                    "--from-layer",
                    "user",
                    "--to-layer",
                    "org",
                    "--skill-id",
                    "user.local.skill.evidence-backed",
                ]
            )

        self.assertEqual(promote_result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["warnings"], [])
        promoted_item = (self.corp_repo / "org" / "skills" / "evidence-backed" / "item.toml").read_text(encoding="utf-8")
        self.assertIn('id = "corp.shadowknight.skill.evidence-backed"', promoted_item)
        self.assertIn("[promotion_checklist]", promoted_item)
        self.assertIn('evidence = "Caught missing downgrade paths in sampled PRs"', promoted_item)

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
                "--user-path",
                str(self.user_layer),
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
