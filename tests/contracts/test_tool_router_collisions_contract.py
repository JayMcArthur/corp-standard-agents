from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from team_agents.errors import ResolutionError
from team_agents.models import ResolutionResult, WorkspaceContext
from team_agents.output import MANAGED_END, MANAGED_START, ROUTER_FILES, write_router_file


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


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_result(workspace: Path, repo_class: str) -> ResolutionResult:
    return ResolutionResult(
        workspace_context=WorkspaceContext(
            workspace=workspace,
            git_root=workspace,
            normalized_remotes=[],
            repo_class=repo_class,
        ),
        layer_chain=["org", "repo-group", "repo", "user"],
        applied_layers=[],
        enabled_sources=[],
        source_details={},
        enabled_skills=[],
        active_policies=[],
        active_docs=[],
        recommended_agent_types=[],
        items={},
    )


class ToolRouterCollisionsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_untracked_targets_are_created_for_all_router_paths(self) -> None:
        workspace = self.root / "workspace-create"
        workspace.mkdir()
        result = make_result(workspace, "internal")
        for router_name in ROUTER_FILES:
            write_router_file(result, workspace, "internal", router_name)
            self.assertTrue((workspace / router_name).exists(), router_name)

    def test_tracked_targets_with_managed_block_are_replaced_in_client_repo(self) -> None:
        workspace = self.root / "workspace-client-managed"
        workspace.mkdir()
        result = make_result(workspace, "client")
        for router_name in ROUTER_FILES:
            path = workspace / router_name
            write(path, f"before\n{MANAGED_START}\nold\n{MANAGED_END}\nafter\n")
            write_router_file(result, workspace, "client", router_name)
            content = path.read_text(encoding="utf-8")
            self.assertIn("before", content)
            self.assertIn("after", content)
            self.assertIn("Use the local generated context under `.agents/`.", content)

    def test_tracked_targets_without_managed_block_append_in_internal_repo(self) -> None:
        workspace = self.root / "workspace-internal-append"
        workspace.mkdir()
        result = make_result(workspace, "internal")
        for router_name in ROUTER_FILES:
            path = workspace / router_name
            write(path, "manual content\n")
            write_router_file(result, workspace, "internal", router_name)
            content = path.read_text(encoding="utf-8")
            self.assertIn("manual content", content)
            self.assertIn(MANAGED_START, content)
            self.assertIn(MANAGED_END, content)

    def test_tracked_targets_without_managed_block_refuse_in_client_repo(self) -> None:
        workspace = self.root / "workspace-client-refuse"
        workspace.mkdir()
        result = make_result(workspace, "client")
        for router_name in ROUTER_FILES:
            path = workspace / router_name
            write(path, "manual content\n")
            with self.assertRaisesRegex(ResolutionError, "cannot be updated"):
                write_router_file(result, workspace, "client", router_name)

