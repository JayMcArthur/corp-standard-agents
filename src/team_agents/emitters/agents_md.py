from __future__ import annotations

from team_agents.bootstrap import bootstrap_guidance_items
from team_agents.models import ResolutionResult


def render_agents_md_contract(result: ResolutionResult) -> str:
    context = result.workspace_context
    repo = context.matched_repo_id or "unknown"
    group = context.matched_repo_group_id or "none"
    profile = context.profile or "none"
    repo_class = context.repo_class or "unknown"
    lines = [
        "# Project Agent Guidance",
        "",
        f"- Repo: `{repo}`",
        f"- Repo group: `{group}`",
        f"- Repo class: `{repo_class}`",
        f"- Active profile/job: `{profile}`",
        "",
        "Generated context lives under `.agents/`. Read `.agents/index.md` first, and use `.agents/resolution.json` for provenance, activation reasons, and source paths.",
        "",
        "## Required Completion Gates",
    ]
    required_completion_gates = [
        item_id
        for item_id in result.active_completion_gates
        if result.items.get(item_id) is not None and result.items[item_id].activation_reason == "required"
    ]
    if required_completion_gates:
        for item_id in required_completion_gates:
            title = result.items[item_id].item.title
            lines.append(f"- `{item_id}`: {title}")
    else:
        lines.append("- None declared.")
    lines.extend(["", "## Minimal Verification"])
    command = minimal_verification_command(result)
    if command:
        lines.extend(["", "```bash", command, "```"])
    else:
        lines.append("- No minimal verification command is declared. Run `team-agents doctor --workspace .` and inspect `.agents/index.md`.")
    evidence = evidence_requirements(result)
    if evidence:
        lines.extend(["", "## Required Evidence Before Done"])
        for item_id, values in evidence:
            lines.append(f"- `{item_id}`: " + ", ".join(f"`{value}`" for value in values))
    prep_flows = preparation_flows(result)
    if prep_flows:
        lines.extend(["", "## Preparation For Complex Work"])
        lines.append("For broad, ambiguous, risky, or multi-file work, use the active preparation playbook before implementation:")
        for flow_id, title in prep_flows:
            lines.append(f"- `{flow_id}`: {title}")
    stop_conditions = stop_condition_rules(result)
    if stop_conditions:
        lines.extend(["", "## Stop Conditions"])
        lines.extend(stop_conditions)
    lines.extend(["", "## Safety"])
    lines.append("- Treat `.agents/` and this managed block as generated local context.")
    lines.append("- Do not commit generated private context unless the repo explicitly tracks it by policy.")
    if repo_class == "client":
        lines.append("- Corporate private operational material must not be pushed into this repo.")
    lines.extend(["", "Expanded skills, policies, contexts, completion gates, playbooks, packs, and profile details stay in `.agents/`; this file stays concise."])
    return "\n".join(lines)


def stop_condition_rules(result: ResolutionResult) -> list[str]:
    lines: list[str] = []
    for profile in result.selected_profile_configs:
        if profile.stop_conditions:
            stops = ", ".join(f"`{value}`" for value in profile.stop_conditions)
            lines.append(f"- Stop and escalate when: {stops}.")
    for item_id in result.active_playbooks:
        resolved = result.items.get(item_id)
        if resolved is None:
            continue
        item = resolved.item
        if not item.stop_conditions:
            continue
        stops = ", ".join(f"`{value}`" for value in item.stop_conditions)
        lines.append(f"- Playbook `{item_id}` stop conditions: {stops}.")
    return lines


def preparation_flows(result: ResolutionResult) -> list[tuple[str, str]]:
    playbooks: list[tuple[str, str]] = []
    for item_id in result.active_playbooks:
        resolved = result.items.get(item_id)
        if resolved is None:
            continue
        tags = {tag.lower() for tag in resolved.item.tags}
        searchable = f"{resolved.item.item_id} {resolved.item.slug} {resolved.item.title}".lower()
        if tags & {"prep", "mise-en-place", "large-task"} or "prep-before-code" in searchable:
            playbooks.append((item_id, resolved.item.title))
    return playbooks


def evidence_requirements(result: ResolutionResult) -> list[tuple[str, list[str]]]:
    requirements: list[tuple[str, list[str]]] = []
    for item_id in result.active_completion_gates + result.active_playbooks:
        resolved = result.items.get(item_id)
        if resolved is not None and resolved.item.evidence_required:
            requirements.append((item_id, resolved.item.evidence_required))
    return requirements


def minimal_verification_command(result: ResolutionResult) -> str | None:
    for resolved in bootstrap_guidance_items(result):
        command = command_after_heading(resolved.item.body, "minimal verification")
        if command:
            return command
    for resolved in bootstrap_guidance_items(result):
        for raw_line in resolved.item.body.splitlines():
            line = raw_line.strip()
            if any(marker in line for marker in ["pytest", "unittest", "npm test", "pnpm test", "cargo test"]):
                return line
    return None


def command_after_heading(body: str, heading: str) -> str | None:
    in_section = False
    in_fence = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            normalized = line.lstrip("#").strip().lower()
            if in_section and normalized != heading:
                return None
            in_section = normalized == heading
            continue
        if not in_section:
            continue
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not line or line.startswith("- "):
            continue
        if in_fence or any(marker in line for marker in ["pytest", "unittest", "npm test", "pnpm test", "cargo test"]):
            return line
    return None
