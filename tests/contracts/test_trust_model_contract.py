from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from team_agents.doctor import run_doctor
from team_agents.errors import ValidationError
from team_agents.loaders import load_corp_repo, load_user_overrides
from team_agents.models import MachineConfig, SourceDefinition
from team_agents.resolution import resolve_workspace
from team_agents.sources import materialize_source
from team_agents.trust import load_trust_store, resolve_trust_status, trust_store_path
from tests.test_team_agents import create_corp_repo, create_external_source_repo, create_user_overrides, init_repo


class TrustModelContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.machine = MachineConfig(
            corp_repo_path=self.root / "corp-control",
            user_override_path=self.root / "user-overrides",
            cache_root=self.home / ".team-agents" / "cache",
            default_tool_target="all",
        )
        self.external_url, self.external_commit = create_external_source_repo(self.root)
        self.corp_repo = create_corp_repo(
            self.root,
            self.external_url,
            self.external_commit,
            "github.com/acme/internal-app",
            "github.com/acme/internal-alt",
            "github.com/acme/client-private",
            "github.com/acme/client-tracked",
        )
        self.user_overrides = create_user_overrides(self.root)
        self.machine.corp_repo_path = self.corp_repo
        self.machine.user_override_path = self.user_overrides
        self.workspace = self.root / "workspace-internal"
        init_repo(self.workspace, "https://github.com/acme/internal-app.git")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_trust_store_path_uses_cache_root(self) -> None:
        expected = self.machine.cache_root / "trust" / "sources.json"
        self.assertEqual(trust_store_path(self.machine), expected)

    def test_pinned_commit_happy_path(self) -> None:
        source = SourceDefinition(
            source_id="shared-ext",
            url=self.external_url,
            commit=self.external_commit,
            namespace="shared",
            trust_mode="pinned-commit",
            path=self.corp_repo / "org" / "sources" / "shared-ext.toml",
            source_type="external",
        )
        source_ref = materialize_source(source, self.machine)
        self.assertEqual(source_ref.commit, self.external_commit)
        self.assertEqual(source_ref.trust_status, "verified-pinned-commit")
        self.assertEqual(source_ref.fingerprint_mode, "computed")

    def test_pin_mismatch_is_rejected(self) -> None:
        source = SourceDefinition(
            source_id="shared-ext",
            url=self.external_url,
            commit=self.external_commit,
            namespace="shared",
            trust_mode="pinned-commit",
            path=self.corp_repo / "org" / "sources" / "shared-ext.toml",
            source_type="external",
        )
        with patch("team_agents.sources.current_head", return_value="0" * 40):
            with self.assertRaisesRegex(ValidationError, "did not resolve to approved commit"):
                materialize_source(source, self.machine)

    def test_tofu_first_contact_records_store(self) -> None:
        source = SourceDefinition(
            source_id="personal-source",
            url="https://example.com/personal.git",
            commit="abcdef1",
            namespace="local",
            trust_mode="pinned-commit",
            path=self.root / "personal-source.toml",
            source_type="user",
        )
        trust_status, fingerprint_mode = resolve_trust_status(source, self.machine, "f" * 64)
        self.assertEqual(trust_status, "recorded-trust-on-first-use")
        self.assertEqual(fingerprint_mode, "tofu")
        store = load_trust_store(self.machine)
        self.assertEqual(store["sources"]["personal-source"]["fingerprint"], "f" * 64)

    def test_tofu_mismatch_on_second_contact_is_rejected(self) -> None:
        source = SourceDefinition(
            source_id="personal-source",
            url="https://example.com/personal.git",
            commit="abcdef1",
            namespace="local",
            trust_mode="pinned-commit",
            path=self.root / "personal-source.toml",
            source_type="user",
        )
        resolve_trust_status(source, self.machine, "f" * 64)
        with self.assertRaisesRegex(ValidationError, "changed fingerprint for pinned commit"):
            resolve_trust_status(source, self.machine, "a" * 64)

    def test_manifest_fingerprint_pass_and_fail(self) -> None:
        source = SourceDefinition(
            source_id="shared-ext",
            url=self.external_url,
            commit=self.external_commit,
            namespace="shared",
            trust_mode="pinned-commit",
            fingerprint="b" * 64,
            path=self.corp_repo / "org" / "sources" / "shared-ext.toml",
            source_type="external",
        )
        status, mode = resolve_trust_status(source, self.machine, "b" * 64)
        self.assertEqual(status, "verified-manifest-fingerprint")
        self.assertEqual(mode, "manifest")
        with self.assertRaisesRegex(ValidationError, "fingerprint mismatch"):
            resolve_trust_status(source, self.machine, "c" * 64)

    def test_trust_metadata_is_exposed_in_resolution_and_doctor_json(self) -> None:
        corp = load_corp_repo(self.corp_repo)
        user = load_user_overrides(self.user_overrides)
        result = resolve_workspace(self.workspace, self.machine, corp, user)
        source_detail = result.to_dict()["source_details"]["shared-ext"]
        self.assertIn("fingerprint", source_detail)
        self.assertIn("fingerprint_mode", source_detail)
        self.assertIn("trust_status", source_detail)

        report = run_doctor(self.machine, self.workspace, self.corp_repo, self.user_overrides, result)
        doctor_source_detail = report["resolution"]["source_details"]["shared-ext"]
        self.assertIn("fingerprint", doctor_source_detail)
        self.assertIn("fingerprint_mode", doctor_source_detail)
        self.assertIn("trust_status", doctor_source_detail)
