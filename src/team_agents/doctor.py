from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from team_agents.bootstrap import bootstrap_guidance_items
from team_agents.errors import TeamAgentsError
from team_agents.emitters.common import MANAGED_END, MANAGED_START
from team_agents.git_tools import find_git_root, has_tracked_prefix, is_tracked, list_normalized_remotes
from team_agents.loaders import load_corp_repo
from team_agents.materialization import effective_materialization_strategy, materialization_warnings
from team_agents.models import MachineConfig, ResolutionResult
from team_agents.output import ROUTER_FILES


def run_doctor(
    machine_config: MachineConfig,
    workspace: Path,
    corp_root: Path,
    user_root: Path,
    resolution: ResolutionResult | None,
    load_error: TeamAgentsError | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    git_root = find_git_root(workspace)
    checks: list[dict[str, str]] = []

    def add_check(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    add_check(
        "machine-config",
        "ok" if machine_config.default_tool_target in {"all", "codex", "claude", "cursor"} else "warn",
        f"tool target is {machine_config.default_tool_target}",
    )
    effective_strategy = effective_materialization_strategy(machine_config.materialization_strategy)
    materialization_warning_list = materialization_warnings(machine_config.materialization_strategy)
    add_check(
        "materialization-strategy",
        "warn" if materialization_warning_list else "ok",
        f"configured {machine_config.materialization_strategy}, effective {effective_strategy}",
    )
    for warning in materialization_warning_list:
        add_check("materialization-support", "warn", warning)
    add_check("corp-repo-path", "ok" if corp_root.exists() else "fail", str(corp_root))
    add_check("user-layer-path", "ok" if user_root.exists() else "fail", str(user_root))

    cache_parent = machine_config.cache_root.parent
    if cache_parent.exists() and os.access(cache_parent, os.W_OK):
        add_check("cache-root-parent", "ok", str(cache_parent))
    else:
        add_check("cache-root-parent", "warn", f"cache parent may not be writable: {cache_parent}")

    if load_error is not None:
        add_check("load-and-resolve", "fail", str(load_error))
    else:
        add_check("load-and-resolve", "ok", "corp repo, local user layer, and workspace resolved")

    if git_root is None:
        add_check("workspace-git", "ok", "workspace is non-git")
    else:
        add_check("workspace-git", "ok", f"git root: {git_root}")
        if has_tracked_prefix(git_root, ".agents"):
            add_check("tracked-generated-content", "fail", "tracked .agents content blocks sync")
        else:
            add_check("tracked-generated-content", "ok", "no tracked .agents content")
        tracked_routers = [name for name in ROUTER_FILES if is_tracked(git_root, name)]
        if tracked_routers:
            add_check("tracked-router-files", "warn", f"tracked router files exist: {', '.join(tracked_routers)}")
            for router_name in tracked_routers:
                path = git_root / router_name
                if path.exists():
                    content = path.read_text(encoding="utf-8")
                    if MANAGED_START in content and MANAGED_END in content:
                        add_check(f"managed-block-{router_name}", "ok", f"{router_name} contains managed block markers")
                    else:
                        add_check(
                            f"managed-block-{router_name}",
                            "warn",
                            f"{router_name} is tracked without managed block markers",
                        )
        else:
            add_check("tracked-router-files", "ok", "router files are untracked or absent")

    policy_compliance: list[dict[str, Any]] = []
    completion_gate_compliance: list[dict[str, Any]] = []
    context_quality_warnings: list[dict[str, str]] = []
    consumer_safety_warnings: list[dict[str, str]] = []
    if resolution is not None:
        repo_match_check = evaluate_workspace_repo_match(corp_root, git_root, resolution)
        if repo_match_check is not None:
            add_check(repo_match_check["name"], repo_match_check["status"], repo_match_check["detail"])
        bootstrap_items = bootstrap_guidance_items(resolution)
        if bootstrap_items:
            add_check(
                "bootstrap-guidance",
                "ok",
                "active bootstrap/minimal verification guidance: "
                + ", ".join(resolved.item.item_id for resolved in bootstrap_items),
            )
        else:
            add_check(
                "bootstrap-guidance",
                "warn",
                "no active repo bootstrap or minimal verification guidance",
            )
        unreviewed_external_skills = [
            item_id
            for item_id in resolution.enabled_skills
            if (resolved := resolution.items.get(item_id)) is not None
            and resolved.item.source_type == "external"
            and resolved.item.trust_level == "unreviewed"
        ]
        if unreviewed_external_skills:
            add_check(
                "unreviewed-external-skills",
                "warn",
                "active external skills are unreviewed: " + ", ".join(unreviewed_external_skills),
            )
        else:
            add_check("unreviewed-external-skills", "ok", "no active unreviewed external skills")
        deprecated_active_items = [
            item_id
            for item_id, resolved in sorted(resolution.items.items())
            if resolved.item.lifecycle_status == "deprecated"
        ]
        if deprecated_active_items:
            add_check(
                "deprecated-active-items",
                "warn",
                "active items are deprecated: " + ", ".join(deprecated_active_items),
            )
        else:
            add_check("deprecated-active-items", "ok", "no active deprecated items")
        policy_compliance = evaluate_policy_compliance(machine_config, user_root, resolution)
        completion_gate_compliance = evaluate_completion_gate_compliance(machine_config, user_root, resolution)
        context_quality_warnings = evaluate_context_quality(resolution)
        for warning in context_quality_warnings:
            add_check(
                f"context-quality:{warning['code']}",
                "warn",
                f"{warning['detail']} Remediation: {warning['remediation']}",
            )
        consumer_safety_warnings = evaluate_consumer_safety_warnings(resolution)
        for warning in consumer_safety_warnings:
            add_check(
                f"consumer-safety:{warning['code']}",
                "warn",
                f"{warning['detail']} Remediation: {warning['remediation']}",
            )
    summary = {
        "ok": sum(1 for check in checks if check["status"] == "ok"),
        "warn": sum(1 for check in checks if check["status"] == "warn"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
    }
    if resolution is not None:
        for entry in policy_compliance + completion_gate_compliance:
            status = "ok" if entry["compliant"] else entry["severity"]
            summary[status] += 1

    result: dict[str, Any] = {
        "machine_config": {
            "corp_repo_path": str(machine_config.corp_repo_path),
            "user_layer_path": str(machine_config.user_layer_path),
            "cache_root": str(machine_config.cache_root),
            "default_tool_target": machine_config.default_tool_target,
            "materialization_strategy": machine_config.materialization_strategy,
            "effective_materialization_strategy": effective_strategy,
        },
        "workspace": {
            "path": str(workspace),
            "git_root": str(git_root) if git_root else None,
        },
        "summary": summary,
        "checks": checks,
        "policy_compliance": policy_compliance,
        "completion_gate_compliance": completion_gate_compliance,
        "context_quality_warnings": context_quality_warnings,
        "consumer_safety_warnings": consumer_safety_warnings,
    }
    if resolution is not None:
        result["resolution"] = {
            "matched_repo_id": resolution.workspace_context.matched_repo_id,
            "matched_repo_group_id": resolution.workspace_context.matched_repo_group_id,
            "profile": resolution.workspace_context.profile,
            "repo_class": resolution.workspace_context.repo_class,
            "is_unknown": resolution.workspace_context.is_unknown,
            "is_non_git": resolution.workspace_context.is_non_git,
            "enabled_sources": resolution.enabled_sources,
            "source_details": {
                source_id: {
                    "commit": source_ref.commit,
                    "url": source_ref.url,
                    "fingerprint": source_ref.fingerprint,
                    "fingerprint_mode": source_ref.fingerprint_mode,
                    "trust_status": source_ref.trust_status,
                }
                for source_id, source_ref in sorted(resolution.source_details.items())
            },
            "enabled_skills": resolution.enabled_skills,
            "active_policies": resolution.active_policies,
            "active_contexts": resolution.active_contexts,
            "active_completion_gates": resolution.active_completion_gates,
            "active_packs": resolution.active_packs,
            "active_playbooks": resolution.active_playbooks,
            "active_profiles": resolution.active_profiles,
            "recommended_items": resolution.recommended_items,
            "recommended_agent_types": resolution.recommended_agent_types,
            "warnings": resolution.warnings,
            "denied_items": {
                item_id: resolved.denied_reason or "disabled or denied"
                for item_id, resolved in sorted(resolution.denied_items.items())
            },
        }
    return result


def evaluate_workspace_repo_match(
    corp_root: Path,
    git_root: Path | None,
    resolution: ResolutionResult,
) -> dict[str, str] | None:
    if git_root is None or resolution.workspace_context.is_non_git:
        return None
    if resolution.workspace_context.matched_repo_id:
        return {
            "name": "workspace-repo-match",
            "status": "ok",
            "detail": f"workspace matched repo {resolution.workspace_context.matched_repo_id}",
        }
    try:
        corp = load_corp_repo(corp_root)
        workspace_remotes = resolution.workspace_context.normalized_remotes or list_normalized_remotes(git_root)
    except TeamAgentsError as exc:
        return {
            "name": "workspace-repo-match",
            "status": "warn",
            "detail": f"could not inspect configured repo remotes: {exc}",
        }
    configured: list[tuple[str, str]] = [
        (repo_id, remote)
        for repo_id, layer in sorted(corp.repos.items())
        for remote in layer.config.normalized_remotes
    ]
    if not workspace_remotes or not configured:
        return None
    candidate = closest_repo_remote(workspace_remotes, configured)
    candidate_detail = ""
    if candidate is not None:
        repo_id, remote = candidate
        candidate_detail = f"; closest configured repo is {repo_id} ({remote})"
    return {
        "name": "workspace-repo-match",
        "status": "warn",
        "detail": "workspace git remotes did not match any configured corp repo: "
        + ", ".join(workspace_remotes)
        + candidate_detail,
    }


def closest_repo_remote(workspace_remotes: list[str], configured: list[tuple[str, str]]) -> tuple[str, str] | None:
    best: tuple[float, str, str] | None = None
    for workspace_remote in workspace_remotes:
        for repo_id, configured_remote in configured:
            score = SequenceMatcher(None, workspace_remote, configured_remote).ratio()
            if best is None or score > best[0]:
                best = (score, repo_id, configured_remote)
    if best is None:
        return None
    return best[1], best[2]


def doctor_text(report: dict[str, Any]) -> str:
    lines = [
        f"workspace: {report['workspace']['path']}",
        f"git-root: {report['workspace']['git_root'] or 'none'}",
        (
            "summary: "
            f"{report['summary']['ok']} ok, "
            f"{report['summary']['warn']} warn, "
            f"{report['summary']['fail']} fail"
        ),
        "",
        "checks:",
    ]
    for check in report["checks"]:
        lines.append(f"- [{check['status']}] {check['name']}: {check['detail']}")
    if "resolution" in report:
        resolution = report["resolution"]
        lines.extend(
            [
                "",
                f"matched-repo: {resolution['matched_repo_id'] or 'unknown'}",
                f"matched-repo-group: {resolution['matched_repo_group_id'] or 'none'}",
                f"profile: {resolution['profile'] or 'none'}",
                f"repo-class: {resolution['repo_class'] or 'unknown'}",
                f"sources: {', '.join(resolution['enabled_sources']) or 'none'}",
                f"skills: {', '.join(resolution['enabled_skills']) or 'none'}",
                f"policies: {', '.join(resolution['active_policies']) or 'none'}",
                f"contexts: {', '.join(resolution['active_contexts']) or 'none'}",
                f"completion gates: {', '.join(resolution['active_completion_gates']) or 'none'}",
                f"packs: {', '.join(resolution['active_packs']) or 'none'}",
                f"playbooks: {', '.join(resolution['active_playbooks']) or 'none'}",
                f"profiles: {', '.join(resolution['active_profiles']) or 'none'}",
                f"recommended-items: {', '.join(resolution['recommended_items']) or 'none'}",
            ]
        )
        if resolution["denied_items"]:
            lines.append(f"denied-items: {', '.join(f'{key} ({value})' for key, value in resolution['denied_items'].items())}")
    if report.get("policy_compliance"):
        lines.extend(["", "policy-compliance:"])
        for entry in report["policy_compliance"]:
            status = "ok" if entry["compliant"] else entry["severity"]
            lines.append(
                f"- [{status}] {entry['item_id']}::{entry['rule']}: {entry['detail']} (remediation: {entry['remediation']})"
            )
    if report.get("completion_gate_compliance"):
        lines.extend(["", "completion-gate-compliance:"])
        for entry in report["completion_gate_compliance"]:
            status = "ok" if entry["compliant"] else entry["severity"]
            lines.append(
                f"- [{status}] {entry['item_id']}::{entry['rule']}: {entry['detail']} (remediation: {entry['remediation']})"
            )
    if report.get("context_quality_warnings"):
        lines.extend(["", "context-quality:"])
        for warning in report["context_quality_warnings"]:
            lines.append(f"- [warn] {warning['code']}: {warning['detail']} (remediation: {warning['remediation']})")
    if report.get("consumer_safety_warnings"):
        lines.extend(["", "consumer-safety:"])
        for warning in report["consumer_safety_warnings"]:
            lines.append(f"- [warn] {warning['code']}: {warning['detail']} (remediation: {warning['remediation']})")
    return "\n".join(lines)


HIGH_RISK_CONSUMERS = {"harness", "harnesses", "workflow-engine", "workflow_engines"}


def evaluate_consumer_safety_warnings(resolution: ResolutionResult) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for profile in resolution.selected_profile_configs:
        high_risk = set(profile.intended_consumers) & HIGH_RISK_CONSUMERS
        if not high_risk:
            continue
        high_risk_labels = sorted(high_risk)
        if not profile.stop_conditions:
            warnings.append(
                {
                    "code": "missing-consumer-stop-conditions",
                    "profile": profile.identifier,
                    "consumers": ", ".join(high_risk_labels),
                    "detail": f"profile {profile.identifier} targets high-risk consumers without stop_conditions",
                    "remediation": "add stop_conditions for harness or workflow-engine use",
                }
            )
    return warnings


def evaluate_context_quality(resolution: ResolutionResult) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    active_ids = sorted(
        set(
            resolution.enabled_skills
            + resolution.active_policies
            + resolution.active_contexts
            + resolution.active_completion_gates
            + resolution.active_packs
            + resolution.active_playbooks
            + resolution.active_profiles
        )
    )
    max_items = context_quality_max_active_items(resolution)
    if len(active_ids) > max_items:
        warnings.append(
            {
                "code": "too-many-active-items",
                "detail": f"{len(active_ids)} active items exceeds threshold {max_items}",
                "remediation": "raise context_quality_max_active_items only when justified, or move broad defaults into profiles, packs, or recommended items",
            }
        )
    missing_provenance = [
        item_id
        for item_id in active_ids
        if (resolved := resolution.items.get(item_id)) is not None
        and (not resolved.item.source_ref or not resolved.item.source_namespace or not resolved.item.item_path)
    ]
    if missing_provenance:
        warnings.append(
            {
                "code": "missing-provenance",
                "detail": "active items lack source provenance: " + ", ".join(missing_provenance),
                "remediation": "load items from Git-backed layers with canonical ids and source paths",
            }
        )
    broad_profile_docs = [
        item_id
        for item_id in resolution.active_contexts
        if (resolved := resolution.items.get(item_id)) is not None
        and selected_by_profile(resolved.activated_by)
        and is_broad_doc(resolved.item.item_id, resolved.item.title, resolved.item.body)
    ]
    if broad_profile_docs:
        warnings.append(
            {
                "code": "profile-broad-contexts",
                "detail": "profile-selected contexts look broad/global without a scoped reason: " + ", ".join(broad_profile_docs),
                "remediation": "replace broad profile contexts with narrower contexts, or keep them recommended until a profile-specific reason exists",
            }
        )
    for kind_name, item_ids in [("context", resolution.active_contexts), ("policy", resolution.active_policies)]:
        duplicates = duplicate_titles(item_ids, resolution)
        for title, duplicate_ids in duplicates.items():
            warnings.append(
                {
                    "code": f"duplicate-{kind_name}s",
                    "detail": f"duplicate or conflicting {kind_name} title {title!r}: {', '.join(duplicate_ids)}",
                    "remediation": "merge duplicate standards or rename/scope them so selection intent is unambiguous",
                }
            )
    verification_contracts = [
        item_id
        for item_id in resolution.active_completion_gates
        if (resolved := resolution.items.get(item_id)) is not None and has_verification_boundary(resolved.item)
    ]
    if not verification_contracts:
        warnings.append(
            {
                "code": "missing-verification-completion-gate",
                "detail": "no active completion gate declares verification or evidence expectations",
                "remediation": "require a definition-of-done or verification completion gate with evidence_required values",
            }
        )
    if (resolution.workspace_context.repo_class or "").lower() == "client":
        boundary_items = [
            item_id
            for item_id in resolution.active_policies + resolution.active_completion_gates
            if (resolved := resolution.items.get(item_id)) is not None and has_client_data_boundary(resolved.item)
        ]
        if not boundary_items:
            warnings.append(
                {
                    "code": "missing-client-data-boundary",
                    "detail": "client repo has no active client-data boundary policy or completion_gate",
                    "remediation": "activate a repo-safe policy or completion_gate covering client data handling before syncing agent context",
                }
            )
    return warnings


def context_quality_max_active_items(resolution: ResolutionResult) -> int:
    for profile in resolution.selected_profile_configs:
        if profile.context_quality_max_active_items is not None:
            return profile.context_quality_max_active_items
    return 40


def selected_by_profile(activated_by: list[str]) -> bool:
    return any(value.startswith("profile:") for value in activated_by)


def is_broad_doc(item_id: str, title: str, body: str) -> bool:
    text = f"{item_id} {title} {body[:500]}".lower()
    return any(marker in text for marker in ["global", "general", "all repos", "everything", "overview"])


def duplicate_titles(item_ids: list[str], resolution: ResolutionResult) -> dict[str, list[str]]:
    by_title: dict[str, list[str]] = {}
    for item_id in item_ids:
        resolved = resolution.items.get(item_id)
        if resolved is None:
            continue
        title = normalize_title(resolved.item.title)
        if title:
            by_title.setdefault(title, []).append(item_id)
    return {title: ids for title, ids in by_title.items() if len(ids) > 1}


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def has_verification_boundary(item: Any) -> bool:
    text = f"{item.item_id} {item.title} {' '.join(item.evidence_required)} {item.body[:1000]}".lower()
    return any(marker in text for marker in ["verification", "verify", "test", "evidence", "definition of done"])


def has_client_data_boundary(item: Any) -> bool:
    text = f"{item.item_id} {item.title} {item.body[:1000]}".lower()
    return any(
        marker in text
        for marker in [
            "client-data",
            "client data",
            "client_data",
            "customer data",
            "data boundary",
            "data handling",
        ]
    )


def doctor_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def evaluate_policy_compliance(
    machine_config: MachineConfig,
    user_root: Path,
    resolution: ResolutionResult,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for policy_id in resolution.active_policies:
        resolved = resolution.items.get(policy_id)
        if resolved is None or not resolved.item.policy_rules:
            continue
        for rule in resolved.item.policy_rules:
            entries.append(
                evaluate_policy_rule(
                    policy_id=policy_id,
                    policy_title=resolved.item.title,
                    item_kind="policy",
                    rule=rule,
                    machine_config=machine_config,
                    user_root=user_root,
                    resolution=resolution,
                )
            )
    return entries


def evaluate_completion_gate_compliance(
    machine_config: MachineConfig,
    user_root: Path,
    resolution: ResolutionResult,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for completion_gate_id in resolution.active_completion_gates:
        resolved = resolution.items.get(completion_gate_id)
        if resolved is None or not resolved.item.policy_rules:
            continue
        for rule in resolved.item.policy_rules:
            entries.append(
                evaluate_policy_rule(
                    policy_id=completion_gate_id,
                    policy_title=resolved.item.title,
                    item_kind="completion_gate",
                    rule=rule,
                    machine_config=machine_config,
                    user_root=user_root,
                    resolution=resolution,
                )
            )
    return entries


def evaluate_policy_rule(
    *,
    policy_id: str,
    policy_title: str,
    item_kind: str,
    rule: dict[str, Any],
    machine_config: MachineConfig,
    user_root: Path,
    resolution: ResolutionResult,
) -> dict[str, Any]:
    rule_name = str(rule["rule"])
    severity = str(rule.get("severity") or "fail")
    remediation = str(rule.get("remediation") or default_policy_remediation(rule_name))
    compliant = True
    detail = "compliant"

    if rule_name == "local_user_layer_must_be_git_backed":
        compliant = (user_root / ".git").exists()
        detail = "local user layer repo is git-backed" if compliant else f"local user layer path is not git-backed: {user_root}"
    elif rule_name == "required_skill_ids":
        required = [str(item) for item in rule.get("skill_ids", [])]
        missing = [item for item in required if item not in resolution.enabled_skills]
        compliant = not missing
        detail = "all required skills are active" if compliant else f"missing required skills: {', '.join(missing)}"
    elif rule_name == "required_completion_gate_ids":
        required = [str(item) for item in rule.get("completion_gate_ids", [])]
        missing = [item for item in required if item not in resolution.active_completion_gates]
        compliant = not missing
        detail = "all required completion gates are active" if compliant else f"missing required completion gates: {', '.join(missing)}"
    elif rule_name == "forbidden_source_patterns":
        patterns = [str(item) for item in rule.get("patterns", [])]
        matches = find_forbidden_source_matches(patterns, resolution)
        compliant = not matches
        detail = "no forbidden source patterns matched" if compliant else f"forbidden sources matched: {', '.join(matches)}"
    else:
        compliant = False
        detail = f"unsupported policy rule: {rule_name}"

    return {
        "item_id": policy_id,
        "item_title": policy_title,
        "item_kind": item_kind,
        "policy_id": policy_id,
        "policy_title": policy_title,
        "rule": rule_name,
        "severity": severity,
        "compliant": compliant,
        "detail": detail,
        "remediation": remediation,
    }


def default_policy_remediation(rule_name: str) -> str:
    defaults = {
        "local_user_layer_must_be_git_backed": "move local user layer into a git-backed repo or initialize git at the configured local user layer path",
        "required_skill_ids": "enable the required skills in the appropriate layer config",
        "required_completion_gate_ids": "enable or require the missing completion gates in the appropriate layer config",
        "forbidden_source_patterns": "remove the matching source or change the corp policy definition",
    }
    return defaults.get(rule_name, "review the corp policy definition")


def find_forbidden_source_matches(patterns: list[str], resolution: ResolutionResult) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        compiled = re.compile(pattern)
        for source_id in resolution.enabled_sources:
            detail = resolution.source_details.get(source_id)
            candidates = [source_id]
            if detail is not None:
                candidates.append(detail.url)
            if any(compiled.search(candidate) for candidate in candidates):
                match = f"{source_id} ({pattern})"
                if match not in matches:
                    matches.append(match)
    return matches
