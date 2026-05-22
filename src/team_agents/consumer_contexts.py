from __future__ import annotations

from team_agents.models import ResolutionResult


def build_harness_context(result: ResolutionResult) -> dict[str, object]:
    resolution = result.to_dict()
    required_completion_gates = {
        item_id: {
            "title": resolved.item.title,
            "evidence_required": resolved.item.evidence_required,
            "activation_reason": resolved.activation_reason,
            "activated_by": resolved.activated_by,
        }
        for item_id in result.active_completion_gates
        if (resolved := result.items.get(item_id)) is not None and resolved.activation_reason == "required"
    }
    active_playbooks = {
        item_id: {
            "title": resolved.item.title,
            "inputs": resolved.item.inputs,
            "outputs": resolved.item.outputs,
            "evidence_required": resolved.item.evidence_required,
            "stop_conditions": resolved.item.stop_conditions,
            "activated_by": resolved.activated_by,
        }
        for item_id in result.active_playbooks
        if (resolved := result.items.get(item_id)) is not None
    }
    evidence_requirements = {
        item_id: resolved.item.evidence_required
        for item_id, resolved in sorted(result.items.items())
        if resolved.item.kind in {"completion_gate", "playbook"} and resolved.item.evidence_required
    }
    profile_stop_conditions = [
        {
            "profile": profile.identifier,
            "stop_conditions": profile.stop_conditions,
            "intended_consumers": profile.intended_consumers,
        }
        for profile in result.selected_profile_configs
        if profile.stop_conditions
    ]
    playbook_stop_conditions = [
        {
            "playbook": item_id,
            "stop_conditions": resolved.item.stop_conditions,
        }
        for item_id in result.active_playbooks
        if (resolved := result.items.get(item_id)) is not None
        if resolved.item.stop_conditions
    ]
    return {
        "schema_version": "v1",
        "kind": "harness-context",
        "non_goals": ["no task runner", "no background orchestration", "no automatic proof validation"],
        "workspace": {
            "path": resolution["workspace"],
            "git_root": resolution["git_root"],
            "repo_id": resolution["matched_repo_id"],
            "repo_group_id": resolution["matched_repo_group_id"],
            "repo_class": resolution["repo_class"],
            "profile": resolution["profile"],
        },
        "resolution_ref": ".agents/resolution.json",
        "selected_profile_configs": resolution["selected_profile_configs"],
        "required_completion_gates": required_completion_gates,
        "active_playbooks": active_playbooks,
        "evidence_requirements": evidence_requirements,
        "stop_condition_sources": {
            "profiles": profile_stop_conditions,
            "playbooks": playbook_stop_conditions,
        },
        "stop_conditions": sorted(
            {value for entry in profile_stop_conditions + playbook_stop_conditions for value in entry["stop_conditions"]}
        ),
        "warnings": result.warnings,
        "denied_items": resolution["denied_items"],
    }


def build_workflow_engine_context(result: ResolutionResult) -> dict[str, object]:
    resolution = result.to_dict()
    active_completion_gates = {
        item_id: {
            "title": item["title"],
            "owner": item.get("owner"),
            "maintainer": item.get("maintainer"),
            "evidence_required": item.get("evidence_required", []),
            "activation_reason": item.get("activation_reason"),
            "activated_by": item.get("activated_by", []),
            "required": item.get("required", False),
        }
        for item_id, item in sorted(resolution["items"].items())
        if item.get("kind") == "completion_gate" and item_id in result.active_completion_gates
    }
    consumable_playbooks = {
        item_id: {
            "title": item["title"],
            "owner": item.get("owner"),
            "maintainer": item.get("maintainer"),
            "inputs": item.get("inputs", []),
            "outputs": item.get("outputs", []),
            "evidence_required": item.get("evidence_required", []),
            "stop_conditions": item.get("stop_conditions", []),
            "activation_reason": item.get("activation_reason"),
            "activated_by": item.get("activated_by", []),
        }
        for item_id, item in sorted(resolution["items"].items())
        if item.get("kind") == "playbook" and item_id in result.active_playbooks
    }
    return {
        "schema_version": "v1",
        "kind": "workflow-engine-context",
        "runtime_boundary": {
            "team_agents_provides": [
                "playbook metadata",
                "resolved profile and job context",
                "active completion gates",
                "evidence requirements",
                "stop conditions",
                "trust and review metadata",
            ],
            "workflow_engine_provides": [
                "workflow graph",
                "node execution",
                "retries",
                "scheduling",
                "state persistence",
                "runtime permission policy and enforcement",
            ],
            "non_goals": [
                "no workflow execution",
                "no graph runtime",
                "no scheduler",
                "no retry engine",
                "no state persistence",
            ],
        },
        "workspace": {
            "path": resolution["workspace"],
            "git_root": resolution["git_root"],
            "repo_id": resolution["matched_repo_id"],
            "repo_group_id": resolution["matched_repo_group_id"],
            "repo_class": resolution["repo_class"],
            "profile": resolution["profile"],
        },
        "integration_surfaces": {
            "context_command": "team-agents context --workspace <path> --profile <profile> --for-workflow-engine --json",
            "resolution_ref": ".agents/resolution.json",
        },
        "selected_profile_configs": resolution["selected_profile_configs"],
        "active_completion_gates": active_completion_gates,
        "playbooks": consumable_playbooks,
        "evidence_requirements": {
            item_id: values
            for item_id, values in {
                **{item_id: completion_gate["evidence_required"] for item_id, completion_gate in active_completion_gates.items()},
                **{item_id: playbook["evidence_required"] for item_id, playbook in consumable_playbooks.items()},
            }.items()
            if values
        },
        "stop_conditions": sorted(
            {value for profile in resolution["selected_profile_configs"] for value in profile.get("stop_conditions", [])}
            | {value for playbook in consumable_playbooks.values() for value in playbook["stop_conditions"]}
        ),
        "warnings": resolution["warnings"],
        "denied_items": resolution["denied_items"],
    }
