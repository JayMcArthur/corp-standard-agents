from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from team_agents.loaders import load_corp_repo, load_user_overrides
from team_agents.models import MachineConfig
from team_agents.output import write_resolution_json
from team_agents.resolution import resolve_workspace
from team_agents.resolution_schema import RESOLUTION_JSON_V1_SCHEMA_PATH, load_resolution_json_schema, validate_resolution_json
from tests.test_team_agents import create_corp_repo, create_external_source_repo, create_user_overrides, init_repo


class ResolutionJsonContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.internal_remote = "github.com/acme/internal-app"
        self.external_url, self.external_commit = create_external_source_repo(self.root)
        self.corp_repo = create_corp_repo(
            self.root,
            self.external_url,
            self.external_commit,
            self.internal_remote,
            "github.com/acme/internal-alt",
            "github.com/acme/client-private",
            "github.com/acme/client-tracked",
        )
        self.user_overrides = create_user_overrides(self.root)
        self.workspace = self.root / "workspace-internal"
        init_repo(self.workspace, f"https://{self.internal_remote}.git")
        self.machine_config = MachineConfig(
            corp_repo_path=self.corp_repo,
            user_override_path=self.user_overrides,
            cache_root=self.home / ".team-agents" / "cache",
            default_tool_target="all",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_schema_file_exists_and_declares_required_top_level_fields(self) -> None:
        self.assertTrue(RESOLUTION_JSON_V1_SCHEMA_PATH.exists())
        schema = load_resolution_json_schema()
        self.assertIn("schema_version", schema["required"])
        self.assertIn("applied_layers", schema["required"])
        self.assertIn("source_details", schema["required"])

    def test_real_resolution_json_validates(self) -> None:
        corp = load_corp_repo(self.corp_repo)
        user = load_user_overrides(self.user_overrides)
        result = resolve_workspace(self.workspace, self.machine_config, corp, user)
        agents_dir = self.workspace / ".agents"
        agents_dir.mkdir()
        path = write_resolution_json(result, agents_dir)
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_resolution_json(payload)
        self.assertEqual(payload["schema_version"], "v1")
        self.assertEqual(payload["matched_repo_id"], "internal-app")
        self.assertEqual(payload["applied_layers"][0]["layer_name"], "org")
        self.assertIn("shared-ext", payload["source_details"])
        self.assertIn("activated_by", payload["items"]["corp.shadowknight.skill.shell-global"])

    def test_missing_top_level_field_is_rejected(self) -> None:
        payload = self._valid_payload()
        del payload["items"]
        with self.assertRaisesRegex(Exception, r"\$\.items is required"):
            validate_resolution_json(payload)

    def test_repo_class_outside_enum_is_rejected(self) -> None:
        payload = self._valid_payload()
        payload["repo_class"] = "bad"
        with self.assertRaisesRegex(Exception, r"\$\.repo_class must be one of"):
            validate_resolution_json(payload)

    def test_item_status_outside_enum_is_rejected(self) -> None:
        payload = self._valid_payload()
        first_item = next(iter(payload["items"].values()))
        first_item["status"] = "mystery"
        with self.assertRaisesRegex(Exception, r"\.status must be one of"):
            validate_resolution_json(payload)

    def _valid_payload(self) -> dict:
        corp = load_corp_repo(self.corp_repo)
        user = load_user_overrides(self.user_overrides)
        result = resolve_workspace(self.workspace, self.machine_config, corp, user)
        return result.to_dict()
