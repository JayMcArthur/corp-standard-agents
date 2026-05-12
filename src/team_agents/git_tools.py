from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from team_agents.errors import GitError, ProtectionError


def run_git(args: list[str], cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def find_git_root(path: Path) -> Path | None:
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.strip()).resolve()


def list_normalized_remotes(repo_root: Path) -> list[str]:
    raw = run_git(["config", "--get-regexp", r"^remote\..*\.url$"], cwd=repo_root, check=False)
    if not raw:
        return []
    remotes: list[str] = []
    for line in raw.splitlines():
        _, url = line.split(" ", 1)
        normalized = normalize_remote(url)
        if normalized not in remotes:
            remotes.append(normalized)
    return remotes


def normalize_remote(url: str) -> str:
    value = url.strip()
    scp_match = re.match(r"^(?P<user>[^@]+)@(?P<host>[^:]+):(?P<path>.+)$", value)
    if scp_match:
        host = scp_match.group("host").lower()
        path = scp_match.group("path")
        return _normalize_host_path(host, path)
    parsed = urlparse(value)
    if parsed.scheme:
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""
        return _normalize_host_path(host, path)
    if ":" in value and "/" not in value.split(":", 1)[0]:
        host, path = value.split(":", 1)
        return _normalize_host_path(host.lower(), path)
    path = value
    if path.endswith(".git"):
        path = path[:-4]
    return path.rstrip("/")


def _normalize_host_path(host: str, path: str) -> str:
    normalized_path = path.strip("/")
    if normalized_path.endswith(".git"):
        normalized_path = normalized_path[:-4]
    if host in {"github.com", "www.github.com"}:
        normalized_path = normalized_path.lower()
    return f"{host}/{normalized_path}".rstrip("/")


def ensure_git_exclude(repo_root: Path, entries: list[str]) -> None:
    info_dir = repo_root / ".git" / "info"
    if not info_dir.exists():
        raise ProtectionError(f"Missing git info directory at {info_dir}")
    exclude_path = info_dir / "exclude"
    existing = exclude_path.read_text(encoding="utf-8").splitlines() if exclude_path.exists() else []
    changed = False
    for entry in entries:
        if entry not in existing:
            existing.append(entry)
            changed = True
    if changed:
        exclude_path.write_text("\n".join(existing) + "\n", encoding="utf-8")


def is_tracked(repo_root: Path, relative_path: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", relative_path],
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def has_tracked_prefix(repo_root: Path, relative_path: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", relative_path],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def current_head(repo_root: Path) -> str:
    return run_git(["rev-parse", "HEAD"], cwd=repo_root)
