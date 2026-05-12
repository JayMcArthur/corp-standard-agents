from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from team_agents.doctor import doctor_json, doctor_text, run_doctor
from team_agents.errors import TeamAgentsError
from team_agents.loaders import load_corp_repo, load_user_overrides
from team_agents.machine import ensure_user_override_layout, load_machine_config, write_machine_config
from team_agents.models import MachineConfig
from team_agents.output import write_sync_output
from team_agents.resolution import resolve_workspace
from team_agents.scaffold import init_corp_repo, init_user_overrides


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except TeamAgentsError as exc:
        print(f"team-agents: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team-agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser("setup")
    setup.add_argument("--corp-repo", required=True, type=Path)
    setup.add_argument("--user-overrides", required=True, type=Path)
    setup.add_argument("--cache-root", type=Path)
    setup.add_argument("--tool-target", default="codex")
    setup.set_defaults(func=cmd_setup)

    sync = subparsers.add_parser("sync")
    sync.add_argument("--workspace", type=Path, default=Path.cwd())
    sync.add_argument("--dry-run", action="store_true")
    sync.set_defaults(func=cmd_sync)

    status = subparsers.add_parser("status")
    status.add_argument("--workspace", type=Path, default=Path.cwd())
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    init_corp = subparsers.add_parser("init-corp-repo")
    init_corp.add_argument("--dest", required=True, type=Path)
    init_corp.set_defaults(func=cmd_init_corp_repo)

    init_user = subparsers.add_parser("init-user-overrides")
    init_user.add_argument("--dest", required=True, type=Path)
    init_user.set_defaults(func=cmd_init_user_overrides)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--workspace", type=Path, default=Path.cwd())
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def cmd_setup(args: argparse.Namespace) -> int:
    corp_repo = args.corp_repo.expanduser().resolve()
    user_override = args.user_overrides.expanduser().resolve()
    cache_root = (args.cache_root or (Path.home() / ".team-agents" / "cache")).expanduser().resolve()
    ensure_user_override_layout(user_override)
    config = MachineConfig(
        corp_repo_path=corp_repo,
        user_override_path=user_override,
        cache_root=cache_root,
        default_tool_target=args.tool_target,
    )
    path = write_machine_config(config)
    print(f"Wrote machine config to {path}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    corp = load_corp_repo(machine_config.corp_repo_path)
    user = load_user_overrides(machine_config.user_override_path)
    result = resolve_workspace(args.workspace, machine_config, corp, user)
    if args.dry_run:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0
    written = write_sync_output(result)
    print(json.dumps({"written": [str(path) for path in written]}, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    corp = load_corp_repo(machine_config.corp_repo_path)
    user = load_user_overrides(machine_config.user_override_path)
    result = resolve_workspace(args.workspace, machine_config, corp, user)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0
    print(f"workspace: {result.workspace_context.workspace}")
    print(f"repo: {result.workspace_context.matched_repo_id or 'unknown'}")
    print(f"repo-group: {result.workspace_context.matched_repo_group_id or 'none'}")
    print(f"repo-class: {result.workspace_context.repo_class or 'unknown'}")
    print(f"sources: {', '.join(result.enabled_sources) or 'none'}")
    print(f"skills: {', '.join(result.enabled_skills) or 'none'}")
    print(f"policies: {', '.join(result.active_policies) or 'none'}")
    print(f"docs: {', '.join(result.active_docs) or 'none'}")
    print(f"recommended-agent-types: {', '.join(result.recommended_agent_types) or 'none'}")
    if result.denied_items:
        denied = ", ".join(
            f"{item_id} ({resolved.denied_reason or 'disabled'})"
            for item_id, resolved in sorted(result.denied_items.items())
        )
        print(f"denied-items: {denied}")
    return 0


def cmd_init_corp_repo(args: argparse.Namespace) -> int:
    dest = args.dest.expanduser().resolve()
    init_corp_repo(dest)
    print(f"Initialized corp control repo skeleton at {dest}")
    return 0


def cmd_init_user_overrides(args: argparse.Namespace) -> int:
    dest = args.dest.expanduser().resolve()
    init_user_overrides(dest)
    print(f"Initialized user overrides skeleton at {dest}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    resolution = None
    load_error: TeamAgentsError | None = None
    try:
        corp = load_corp_repo(machine_config.corp_repo_path)
        user = load_user_overrides(machine_config.user_override_path)
        resolution = resolve_workspace(args.workspace, machine_config, corp, user)
    except TeamAgentsError as exc:
        load_error = exc
    report = run_doctor(
        machine_config=machine_config,
        workspace=args.workspace,
        corp_root=machine_config.corp_repo_path,
        user_root=machine_config.user_override_path,
        resolution=resolution,
        load_error=load_error,
    )
    if args.json:
        print(doctor_json(report))
    else:
        print(doctor_text(report))
    return 1 if report["summary"]["fail"] else 0
