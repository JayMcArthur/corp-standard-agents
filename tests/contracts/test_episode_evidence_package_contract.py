from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "specs" / "v1" / "episode-evidence-package.md"


class EpisodeEvidencePackageContractTests(unittest.TestCase):
    def test_episode_evidence_package_shape_is_documented(self) -> None:
        content = SPEC.read_text(encoding="utf-8")

        for path in [
            ".agents/episode/",
            "task.md",
            "context-used.json",
            "verification.md",
            "risks.md",
            "decisions.md",
        ]:
            with self.subTest(path=path):
                self.assertIn(path, content)

    def test_episode_package_maps_contract_evidence_keys(self) -> None:
        content = SPEC.read_text(encoding="utf-8")

        for evidence_key in [
            "tests_run",
            "files_changed_summary",
            "risk_notes",
            "verification_command_output",
            "context_grounding",
            "task_decomposition",
            "acceptance_criteria",
            "verification_plan",
        ]:
            with self.subTest(evidence_key=evidence_key):
                self.assertIn(evidence_key, content)


if __name__ == "__main__":
    unittest.main()
