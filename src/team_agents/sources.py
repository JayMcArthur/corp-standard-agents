from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from team_agents.errors import GitError, ValidationError
from team_agents.git_tools import current_head, run_git
from team_agents.loaders import load_items
from team_agents.models import Item, MachineConfig, SourceDefinition, SourceRef
from team_agents.trust import compute_checkout_fingerprint, resolve_trust_status


def materialize_source(source: SourceDefinition, machine_config: MachineConfig) -> SourceRef:
    target = machine_config.cache_root / "sources" / source.source_id / source.commit
    checkout = target / "checkout"
    target.mkdir(parents=True, exist_ok=True)
    if checkout.exists():
        try:
            head = current_head(checkout)
        except GitError:
            shutil.rmtree(checkout)
            head = ""
        if head != source.commit:
            run_git(["fetch", "--all", "--tags"], cwd=checkout, check=False)
            run_git(["checkout", "--detach", source.commit], cwd=checkout)
    else:
        proc = subprocess.run(
            ["git", "clone", source.url, str(checkout)],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise GitError(proc.stderr.strip() or proc.stdout.strip() or f"Failed to clone {source.url}")
        run_git(["checkout", "--detach", source.commit], cwd=checkout)
    head = current_head(checkout)
    if head != source.commit:
        raise ValidationError(f"Source {source.source_id} did not resolve to approved commit {source.commit}")
    fingerprint = compute_checkout_fingerprint(checkout)
    trust_status, fingerprint_mode = resolve_trust_status(source, machine_config, fingerprint)
    return SourceRef(
        source_id=source.source_id,
        source_type=source.source_type,
        namespace=source.namespace,
        commit=source.commit,
        checkout_path=checkout,
        url=source.url,
        fingerprint=fingerprint,
        fingerprint_mode=fingerprint_mode,
        trust_status=trust_status,
    )


def load_source_items(source: SourceDefinition, source_ref: SourceRef) -> dict[str, Item]:
    items = load_items(source_ref.checkout_path, source_type=source.source_type, source_namespace=source.namespace)
    for item in items.values():
        item.source_namespace = source.namespace
        item.source_ref = source.commit
    return items
