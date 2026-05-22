from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ConsumerDocsContractTests(unittest.TestCase):
    def test_consumer_docs_cover_produce_consume_examples_and_boundaries(self) -> None:
        for name in [
            "corp-maintainers.md",
            "developers.md",
            "harnesses.md",
            "workflow-engines.md",
            "ci-governance.md",
        ]:
            with self.subTest(name=name):
                path = ROOT / "docs" / "consumers" / name
                self.assertTrue(path.exists(), path)
                text = path.read_text(encoding="utf-8")
                self.assertIn("## Produces", text)
                self.assertIn("## Consumes", text)
                self.assertIn("## Boundaries", text)
                self.assertIn("team-agents", text)
