from __future__ import annotations

from team_agents.models import ResolutionResult, ResolvedItem


BOOTSTRAP_TAGS = {"bootstrap", "repo-bootstrap", "minimal-verification"}


def is_bootstrap_guidance(resolved: ResolvedItem) -> bool:
    item = resolved.item
    if item.kind not in {"completion_gate", "playbook", "context"}:
        return False
    tags = {tag.lower() for tag in item.tags}
    if tags & BOOTSTRAP_TAGS:
        return True
    searchable = f"{item.item_id} {item.slug} {item.title} {item.body}".lower()
    return "repo bootstrap" in searchable or "minimal verification" in searchable


def bootstrap_guidance_items(result: ResolutionResult) -> list[ResolvedItem]:
    active_ids = set(result.active_completion_gates + result.active_playbooks + result.active_contexts)
    return [
        resolved
        for item_id, resolved in sorted(result.items.items())
        if item_id in active_ids and resolved.active and is_bootstrap_guidance(resolved)
    ]


def render_bootstrap_guidance(items: list[ResolvedItem]) -> str:
    lines = [
        "# Repo Bootstrap Guidance",
        "",
        "Verified startup and minimal verification guidance for this workspace.",
    ]
    for resolved in items:
        item = resolved.item
        lines.extend(
            [
                "",
                f"## {item.title}",
                "",
                f"- ID: `{item.item_id}`",
                f"- Kind: `{item.kind}`",
                f"- Activation: `{resolved.activation_reason or 'active'}`",
                "",
                item.body.strip(),
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
