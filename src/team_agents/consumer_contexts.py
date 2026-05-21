from __future__ import annotations

from team_agents.models import ResolutionResult


def build_harness_context(result: ResolutionResult) -> dict[str, object]:
    resolution = result.to_dict()
    required_contracts = {
        item_id: {
            "title": resolved.item.title,
            "evidence_required": resolved.item.evidence_required,
            "activation_reason": resolved.activation_reason,
            "activated_by": resolved.activated_by,
        }
        for item_id in result.active_contracts
        if (resolved := result.items.get(item_id)) is not None and resolved.activation_reason == "required"
    }
    active_flows = {
        item_id: {
            "title": resolved.item.title,
            "inputs": resolved.item.inputs,
            "outputs": resolved.item.outputs,
            "evidence_required": resolved.item.evidence_required,
            "stop_conditions": resolved.item.stop_conditions,
            "activated_by": resolved.activated_by,
        }
        for item_id in result.active_flows
        if (resolved := result.items.get(item_id)) is not None
    }
    evidence_requirements = {
        item_id: resolved.item.evidence_required
        for item_id, resolved in sorted(result.items.items())
        if resolved.item.kind in {"contract", "flow"} and resolved.item.evidence_required
    }
    profile_permissions = [
        {
            "profile": profile.identifier,
            "autonomy_level": profile.autonomy_level,
            "requires_human_approval": profile.requires_human_approval,
            "stop_conditions": profile.stop_conditions,
            "escalation_contact": profile.escalation_contact,
            "allowed_tool_classes": profile.allowed_tool_classes,
            "requires_approval_for": profile.requires_approval_for,
            "forbidden_tool_classes": profile.forbidden_tool_classes,
            "intended_consumers": profile.intended_consumers,
        }
        for profile in result.selected_profile_configs
    ]
    flow_permissions = [
        {
            "flow": item_id,
            "autonomy_level": resolved.item.autonomy_level,
            "requires_human_approval": resolved.item.requires_human_approval,
            "stop_conditions": resolved.item.stop_conditions,
            "escalation_contact": resolved.item.escalation_contact,
            "allowed_tool_classes": resolved.item.allowed_tool_classes,
            "requires_approval_for": resolved.item.requires_approval_for,
            "forbidden_tool_classes": resolved.item.forbidden_tool_classes,
        }
        for item_id in result.active_flows
        if (resolved := result.items.get(item_id)) is not None
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
        "required_contracts": required_contracts,
        "active_flows": active_flows,
        "evidence_requirements": evidence_requirements,
        "tool_permissions": {
            "profiles": profile_permissions,
            "flows": flow_permissions,
        },
        "stop_conditions": sorted(
            {value for entry in profile_permissions + flow_permissions for value in entry["stop_conditions"]}
        ),
        "warnings": result.warnings,
        "denied_items": resolution["denied_items"],
    }


def build_agent_os_context(result: ResolutionResult) -> dict[str, object]:
    resolution = result.to_dict()
    generated_targets: dict[str, list[str]] = {"claude": [], "codex": [], "cursor": []}
    trust_review_metadata = {}
    for item_id, item in sorted(resolution["items"].items()):
        for target in item.get("target_outputs", []):
            generated_targets.setdefault(target, []).append(item_id)
        trust_review_metadata[item_id] = {
            key: item[key]
            for key in [
                "kind",
                "title",
                "source_type",
                "source_namespace",
                "source_ref",
                "trust_level",
                "review_status",
                "privacy_status",
                "lifecycle_status",
                "status",
                "activation_state",
            ]
            if key in item
        }
    return {
        "schema_version": "v1",
        "kind": "agent-os-context",
        "runtime_boundary": {
            "team_agents_provides": [
                "standards registry",
                "resolved profile and job context",
                "trust and review metadata",
                "contracts and evidence requirements",
                "flows as playbooks",
                "generated target files",
            ],
            "agent_os_provides": [
                "task state",
                "handoffs",
                "memory",
                "scheduling",
                "runtime permissions",
                "intervention logs",
            ],
            "non_goals": [
                "no task state",
                "no handoff state",
                "no memory store",
                "no scheduling",
                "no runtime permission engine",
                "no intervention log",
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
            "registry_command": "team-agents registry --json",
            "context_command": "team-agents context --workspace <path> --for-agent-os --json",
            "resolution_ref": ".agents/resolution.json",
            "generated_target_files": ["AGENTS.md", "CLAUDE.md", ".cursor/rules/team-agents.mdc"],
        },
        "selected_profile_configs": resolution["selected_profile_configs"],
        "active_standards": {
            "skills": resolution["enabled_skills"],
            "policies": resolution["active_policies"],
            "docs": resolution["active_docs"],
            "contracts": resolution["active_contracts"],
            "packs": resolution["active_packs"],
            "flows": resolution["active_flows"],
            "profiles": resolution["active_profiles"],
        },
        "contracts": {
            item_id: {
                "title": item["title"],
                "evidence_required": item.get("evidence_required", []),
                "activation_reason": item.get("activation_reason"),
                "activated_by": item.get("activated_by", []),
            }
            for item_id, item in sorted(resolution["items"].items())
            if item.get("kind") == "contract"
        },
        "flows_as_playbooks": {
            item_id: {
                "title": item["title"],
                "inputs": item.get("inputs", []),
                "outputs": item.get("outputs", []),
                "evidence_required": item.get("evidence_required", []),
                "stop_conditions": item.get("stop_conditions", []),
                "activation_reason": item.get("activation_reason"),
                "activated_by": item.get("activated_by", []),
            }
            for item_id, item in sorted(resolution["items"].items())
            if item.get("kind") == "flow"
        },
        "trust_review_metadata": trust_review_metadata,
        "source_details": resolution["source_details"],
        "generated_targets": {target: sorted(item_ids) for target, item_ids in sorted(generated_targets.items())},
        "warnings": resolution["warnings"],
        "denied_items": resolution["denied_items"],
    }


def build_workflow_engine_context(result: ResolutionResult) -> dict[str, object]:
    resolution = result.to_dict()
    active_contracts = {
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
        if item.get("kind") == "contract" and item_id in result.active_contracts
    }
    consumable_flows = {
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
            "autonomy_level": item.get("autonomy_level", "interactive"),
            "requires_human_approval": item.get("requires_human_approval", []),
            "requires_approval_for": item.get("requires_approval_for", []),
            "forbidden_tool_classes": item.get("forbidden_tool_classes", []),
        }
        for item_id, item in sorted(resolution["items"].items())
        if item.get("kind") == "flow" and item_id in result.active_flows
    }
    return {
        "schema_version": "v1",
        "kind": "workflow-engine-context",
        "runtime_boundary": {
            "team_agents_provides": [
                "flow playbook metadata",
                "resolved profile and job context",
                "active contracts",
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
                "runtime permission enforcement",
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
        "active_contracts": active_contracts,
        "flows": consumable_flows,
        "evidence_requirements": {
            item_id: values
            for item_id, values in {
                **{item_id: contract["evidence_required"] for item_id, contract in active_contracts.items()},
                **{item_id: flow["evidence_required"] for item_id, flow in consumable_flows.items()},
            }.items()
            if values
        },
        "stop_conditions": sorted(
            {value for profile in resolution["selected_profile_configs"] for value in profile.get("stop_conditions", [])}
            | {value for flow in consumable_flows.values() for value in flow["stop_conditions"]}
        ),
        "warnings": resolution["warnings"],
        "denied_items": resolution["denied_items"],
    }
