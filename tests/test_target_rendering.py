from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from team_agents.emitters.claude import render_skill_markdown
from team_agents.emitters.agents_md import render_agents_md_contract
from team_agents.library import render_codex_section, render_cursor_rule, target_included
from team_agents.models import Item, LayerConfig, ResolvedItem, ResolutionResult, TargetSettings, WorkspaceContext


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden" / "target_rendering"


class TargetRenderingTests(unittest.TestCase):
    def test_claude_codex_and_cursor_target_golden_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".materialization-strategy").write_text("render-only\n", encoding="utf-8")
            item = make_item(root)

            self.assertEqual(render_skill_markdown(item), read_golden("claude_skill.md"))
            self.assertEqual(render_codex_section(root, item) + "\n", read_golden("codex_short.md"))
            self.assertEqual(render_cursor_rule(item), read_golden("cursor_rule.mdc"))

    def test_target_include_exclude_overrides_legacy_target_tools(self) -> None:
        item = make_item(Path("/tmp/source"))
        self.assertFalse(target_included(item, "claude"))
        self.assertTrue(target_included(item, "codex"))
        self.assertTrue(target_included(item, "cursor"))

    def test_agents_md_contract_golden_output(self) -> None:
        result = make_resolution_result(Path("/tmp/source"))
        self.assertEqual(render_agents_md_contract(result) + "\n", read_golden("agents_md_contract.md"))

    def test_agents_md_contract_includes_stop_rules(self) -> None:
        result = make_resolution_result(Path("/tmp/source"))
        result.selected_profile_configs = [
            LayerConfig(
                layer_name="profile",
                layer_path=Path("/tmp/source/profiles/coder.toml"),
                identifier="coder",
                stop_conditions=["secrets_detected", "unclear_requirement"],
            )
        ]
        rendered = render_agents_md_contract(result)
        self.assertIn("## Stop Conditions", rendered)
        self.assertIn("Stop and escalate when: `secrets_detected`, `unclear_requirement`", rendered)


def make_item(root: Path) -> Item:
    body = "First paragraph for every tool.\n\nSecond paragraph should remain in Claude output.\n"
    return Item(
        item_id="user.local.skill.reviewer",
        kind="skill",
        title="Reviewer",
        privacy="repo-safe",
        source_type="user",
        source_namespace="local",
        source_ref=str(root),
        body=body,
        slug="reviewer",
        item_path=root / "skills" / "reviewer" / "item.toml",
        body_path=root / "skills" / "reviewer" / "body.md",
        target_tools=["claude"],
        target_settings={
            "claude": TargetSettings(mode="skill", include=False),
            "codex": TargetSettings(mode="agents-section", include=True, summary_budget="short"),
            "cursor": TargetSettings(mode="rule", include=True, globs=["src/**/*.py"], always_apply=True),
        },
    )


def read_golden(name: str) -> str:
    return (GOLDEN / name).read_text(encoding="utf-8")


def make_resolution_result(root: Path) -> ResolutionResult:
    done = Item(
        item_id="corp.example.completion_gate.definition-of-done",
        kind="completion_gate",
        title="Definition Of Done",
        privacy="repo-safe",
        source_type="corp",
        source_namespace="example",
        source_ref=str(root),
        body="Done means verified.",
        slug="definition-of-done",
        item_path=root / "completion_gates" / "definition-of-done" / "item.toml",
        body_path=root / "completion_gates" / "definition-of-done" / "body.md",
    )
    bootstrap = Item(
        item_id="corp.example.completion_gate.repo-bootstrap",
        kind="completion_gate",
        title="Repo Bootstrap",
        privacy="repo-safe",
        source_type="corp",
        source_namespace="example",
        source_ref=str(root),
        body="""# Repo Bootstrap

## Minimal Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
""",
        slug="repo-bootstrap",
        item_path=root / "completion_gates" / "repo-bootstrap" / "item.toml",
        body_path=root / "completion_gates" / "repo-bootstrap" / "body.md",
        tags=["bootstrap"],
    )
    prep = Item(
        item_id="corp.example.playbook.prep-before-code",
        kind="playbook",
        title="Prep Before Code",
        privacy="repo-safe",
        source_type="corp",
        source_namespace="example",
        source_ref=str(root),
        body="Prepare before coding.",
        slug="prep-before-code",
        item_path=root / "playbooks" / "prep-before-code" / "item.toml",
        body_path=root / "playbooks" / "prep-before-code" / "body.md",
        tags=["prep", "mise-en-place"],
    )
    items = {
        done.item_id: ResolvedItem(
            item=done,
            layer_name="org",
            status="direct",
            activated_by=["org:example"],
            activation_reason="required",
        ),
        bootstrap.item_id: ResolvedItem(
            item=bootstrap,
            layer_name="repo",
            status="direct",
            activated_by=["repo:api"],
            activation_reason="required",
        ),
        prep.item_id: ResolvedItem(
            item=prep,
            layer_name="profile",
            status="direct",
            activated_by=["profile:coder"],
            activation_reason="enabled",
        ),
    }
    return ResolutionResult(
        workspace_context=WorkspaceContext(
            workspace=Path("/workspace/api"),
            git_root=Path("/workspace/api"),
            normalized_remotes=["git.example.test/team/api"],
            matched_repo_id="api",
            matched_repo_group_id="platform",
            repo_class="internal",
            profile="coder",
        ),
        layer_chain=["org", "repo-group", "repo", "profile", "user"],
        applied_layers=[],
        enabled_sources=[],
        source_details={},
        enabled_skills=[],
        active_policies=[],
        active_contexts=[],
        active_completion_gates=[done.item_id, bootstrap.item_id],
        active_packs=[],
        active_playbooks=[prep.item_id],
        active_profiles=[],
        recommended_items=[],
        recommended_agent_types=[],
        items=items,
    )
