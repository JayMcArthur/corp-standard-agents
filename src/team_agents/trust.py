from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from team_agents.errors import ValidationError
from team_agents.models import MachineConfig, SourceDefinition


def trust_store_path(machine_config: MachineConfig) -> Path:
    return machine_config.cache_root / "trust" / "sources.json"


def load_trust_store(machine_config: MachineConfig) -> dict[str, Any]:
    path = trust_store_path(machine_config)
    if not path.exists():
        return {"sources": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_trust_store(machine_config: MachineConfig, store: dict[str, Any]) -> None:
    path = trust_store_path(machine_config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compute_checkout_fingerprint(checkout_path: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in checkout_path.rglob("*") if p.is_file() and ".git" not in p.parts):
        relative = path.relative_to(checkout_path).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_trust_status(
    source: SourceDefinition,
    machine_config: MachineConfig,
    actual_fingerprint: str,
) -> tuple[str, str]:
    if source.fingerprint:
        if source.fingerprint != actual_fingerprint:
            raise ValidationError(
                f"Source {source.source_id} fingerprint mismatch: expected {source.fingerprint}, got {actual_fingerprint}"
            )
        return "verified-manifest-fingerprint", "manifest"

    if source.source_type != "user":
        return "verified-pinned-commit", "computed"

    store = load_trust_store(machine_config)
    sources = store.setdefault("sources", {})
    existing = sources.get(source.source_id)
    now = datetime.now(UTC).isoformat()
    if existing is None:
        sources[source.source_id] = {
            "url": source.url,
            "commit": source.commit,
            "fingerprint": actual_fingerprint,
            "first_seen_at": now,
            "last_seen_at": now,
            "trust_mode": "trust-on-first-use",
        }
        save_trust_store(machine_config, store)
        return "recorded-trust-on-first-use", "tofu"
    if existing["url"] != source.url:
        raise ValidationError(f"User source {source.source_id} changed URL from {existing['url']} to {source.url}")
    if existing["commit"] == source.commit and existing["fingerprint"] != actual_fingerprint:
        raise ValidationError(
            f"User source {source.source_id} changed fingerprint for pinned commit {source.commit}"
        )
    existing["commit"] = source.commit
    existing["fingerprint"] = actual_fingerprint
    existing["last_seen_at"] = now
    save_trust_store(machine_config, store)
    return "verified-trust-on-first-use", "tofu"
