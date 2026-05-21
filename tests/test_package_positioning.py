from pathlib import Path
import tomllib
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class PackagePositioningTests(unittest.TestCase):
    def test_pyproject_metadata_uses_standards_layer_positioning(self) -> None:
        metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = metadata["project"]

        self.assertEqual(project["description"], "Git-backed standards layer for AI tools.")
        self.assertGreaterEqual(
            set(project["keywords"]),
            {"standards", "policies", "context", "claude", "codex", "cursor"},
        )

    def test_readme_explains_current_public_positioning(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("`team-agents` is a Git-backed standards layer for AI tools.", readme)
        self.assertIn("not an Agent OS", readme)
        self.assertIn("orchestrator", readme)
        self.assertIn("bash scripts/bootstrap_examples.sh", readme)
        self.assertIn("Author A Standard", readme)
        self.assertIn("local user layer", readme.lower())
        self.assertIn("profiles and jobs", readme.lower())
        self.assertIn("Integration Views", readme)

    def test_product_docs_do_not_point_to_completed_task_lists(self) -> None:
        for relative in ["README.md", "CONTEXT.md", "CONTRIBUTING.md", "CHANGELOG.md"]:
            with self.subTest(relative=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertNotIn("to_consume", text)
                self.assertNotIn("docs/requirements", text)
                self.assertNotIn("init-user-overrides", text)

    def test_completed_planning_artifacts_are_not_packaged_as_product_docs(self) -> None:
        for relative in [
            "to_consume",
            "docs/requirements",
            "team_agents_private_pack_v3.md",
            "v3_change_list_for_requirements_spec.md",
        ]:
            with self.subTest(relative=relative):
                self.assertFalse((REPO_ROOT / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()
