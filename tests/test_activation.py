from __future__ import annotations

import unittest
from pathlib import Path

from team_agents.activation import select_activations
from team_agents.models import Item, LayerConfig, LayerData, ResolvedItem


class ActivationSelectionTests(unittest.TestCase):
    def test_pack_expansion_records_required_enabled_and_provenance(self) -> None:
        root = Path("/tmp/corp")
        pack_id = "corp.example.pack.baseline"
        policy_id = "corp.example.policy.no-leaks"
        skill_id = "corp.example.skill.review"
        playbook_id = "corp.example.playbook.prep"
        layers = [
            LayerData(
                config=LayerConfig(
                    layer_name="org",
                    layer_path=root / "org",
                    identifier="example",
                    required_packs=[pack_id],
                ),
                items={},
            )
        ]
        resolved_items = {
            pack_id: ResolvedItem(
                item=make_item(root, pack_id, "pack", required=[policy_id], enabled=[skill_id, playbook_id]),
                layer_name="org",
                status="direct",
            ),
            policy_id: ResolvedItem(item=make_item(root, policy_id, "policy"), layer_name="org", status="direct"),
            skill_id: ResolvedItem(item=make_item(root, skill_id, "skill"), layer_name="org", status="direct"),
            playbook_id: ResolvedItem(item=make_item(root, playbook_id, "playbook"), layer_name="org", status="direct"),
        }

        selection = select_activations(
            activation_layers=layers,
            resolved_items=resolved_items,
            org_config=layers[0].config,
            user_config=LayerConfig(layer_name="user", layer_path=root / "user", identifier="local"),
            is_unknown_workspace=False,
        )

        self.assertEqual(selection.active_pack_ids, [pack_id])
        self.assertIn(policy_id, selection.active_policy_ids)
        self.assertIn(skill_id, selection.enabled_skills)
        self.assertIn(playbook_id, selection.active_playbook_ids)
        self.assertEqual(selection.activation_reasons[policy_id], "required")
        self.assertEqual(selection.activation_reasons[skill_id], "enabled")
        self.assertIn("org:example", selection.activation_map[pack_id])
        self.assertIn(f"pack:{pack_id}", selection.activation_map[policy_id])
        self.assertIn(policy_id, selection.required_item_ids)

    def test_unknown_workspace_uses_minimal_org_and_user_selection(self) -> None:
        root = Path("/tmp/corp")
        org_skill = "corp.example.skill.repo-onboarding"
        user_skill = "user.local.skill.personal"
        org = LayerConfig(
            layer_name="org",
            layer_path=root / "org",
            identifier="example",
            enabled_skills=["corp.example.skill.global"],
            minimal_enabled_skills=[org_skill],
        )
        user = LayerConfig(
            layer_name="user",
            layer_path=root / "user",
            identifier="local",
            enabled_skills=[user_skill],
        )
        layers = [
            LayerData(config=org, items={}),
            LayerData(config=user, items={}),
        ]

        selection = select_activations(
            activation_layers=layers,
            resolved_items={},
            org_config=org,
            user_config=user,
            is_unknown_workspace=True,
        )

        self.assertEqual(selection.enabled_skills, {org_skill, user_skill})
        self.assertNotIn("corp.example.skill.global", selection.enabled_skills)
        self.assertEqual(selection.activation_map[org_skill], ["org:example"])
        self.assertEqual(selection.activation_map[user_skill], ["user:local"])


def make_item(
    root: Path,
    item_id: str,
    kind: str,
    *,
    required: list[str] | None = None,
    enabled: list[str] | None = None,
) -> Item:
    return Item(
        item_id=item_id,
        kind=kind,
        title=item_id.rsplit(".", 1)[-1].replace("-", " ").title(),
        privacy="repo-safe",
        source_type="corp",
        source_namespace="example",
        source_ref=str(root),
        body="Body",
        slug=item_id.rsplit(".", 1)[-1],
        item_path=root / kind / item_id / "item.toml",
        body_path=root / kind / item_id / "body.md",
        activation_required=list(required or []),
        activation_enabled=list(enabled or []),
    )


if __name__ == "__main__":
    unittest.main()
