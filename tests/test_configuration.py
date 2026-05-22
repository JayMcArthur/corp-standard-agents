from __future__ import annotations

import unittest
from pathlib import Path

from team_agents.configuration import detect_skill_collisions, merge_delta_values, unique_list
from team_agents.models import Item, ResolvedItem, ResolutionResult, WorkspaceContext


class ConfigurationTests(unittest.TestCase):
    def test_merge_delta_values_applies_additions_and_removals_in_order(self) -> None:
        self.assertEqual(
            merge_delta_values(["a", "b"], ["b", "c"], ["a"]),
            ["b", "c"],
        )

    def test_unique_list_preserves_first_seen_order(self) -> None:
        self.assertEqual(unique_list(["a", "b", "a", "c", "b"]), ["a", "b", "c"])

    def test_detect_skill_collisions_respects_target_overlap(self) -> None:
        first = make_skill("corp.example.skill.review", target_tools=["claude"])
        second = make_skill("user.local.skill.review", target_tools=["claude"])
        cursor_only = make_skill("corp.example.skill.review-cursor", slug="review", target_tools=["cursor"])
        result = ResolutionResult(
            workspace_context=WorkspaceContext(
                workspace=Path("/workspace"),
                git_root=Path("/workspace"),
                normalized_remotes=[],
            ),
            layer_chain=[],
            applied_layers=[],
            enabled_sources=[],
            source_details={},
            enabled_skills=[],
            active_policies=[],
            active_contexts=[],
            active_completion_gates=[],
            active_packs=[],
            active_playbooks=[],
            active_profiles=[],
            recommended_items=[],
            recommended_agent_types=[],
            items={
                first.item_id: ResolvedItem(item=first, layer_name="org", status="direct"),
                second.item_id: ResolvedItem(item=second, layer_name="user", status="direct"),
                cursor_only.item_id: ResolvedItem(item=cursor_only, layer_name="org", status="direct"),
            },
        )

        collisions = detect_skill_collisions(result)

        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0]["slug"], "review")
        self.assertEqual(
            [item["item_id"] for item in collisions[0]["items"]],
            ["corp.example.skill.review", "user.local.skill.review"],
        )


def make_skill(item_id: str, *, slug: str | None = None, target_tools: list[str] | None = None) -> Item:
    root = Path("/tmp/source")
    item_slug = slug or item_id.rsplit(".", 1)[-1]
    return Item(
        item_id=item_id,
        kind="skill",
        title=item_slug.title(),
        privacy="repo-safe",
        source_type="corp",
        source_namespace="example",
        source_ref=str(root),
        body="Body",
        slug=item_slug,
        item_path=root / "skills" / item_slug / "item.toml",
        body_path=root / "skills" / item_slug / "body.md",
        target_tools=list(target_tools or []),
    )


if __name__ == "__main__":
    unittest.main()
