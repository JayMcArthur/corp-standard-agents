from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from team_agents.doctor import doctor_json, doctor_text, run_doctor
from team_agents.errors import TeamAgentsError
from team_agents.loaders import load_corp_repo, load_user_overrides
from team_agents.importers import import_folder_skills
from team_agents.machine import ensure_user_override_layout, load_machine_config, write_machine_config
from team_agents.models import MachineConfig
from team_agents.output import write_sync_output
from team_agents.promotion import promote_skills
from team_agents.repo_registry import register_repo
from team_agents.resolution import resolve_workspace
from team_agents.scaffold import init_corp_repo, init_user_overrides
from team_agents.source_registry import enable_source_in_layer, register_corp_source, register_user_source, resolve_layer_root


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
    setup.add_argument("--tool-target", choices=["all", "codex", "claude"], default="all")
    setup.add_argument("--init-corp-if-missing", action="store_true")
    setup.add_argument("--init-user-if-missing", action="store_true")
    setup.add_argument("--import-skills-from", type=Path)
    setup.add_argument("--import-skills-to", choices=["user", "org", "repo"], default="user")
    setup.add_argument("--import-codex-skills-from", dest="import_skills_from", type=Path, help=argparse.SUPPRESS)
    setup.add_argument("--import-codex-skills-to", dest="import_skills_to", choices=["user", "org", "repo"], help=argparse.SUPPRESS)
    setup.add_argument("--include-system-skills", action="store_true")
    setup.add_argument("--workspace", type=Path)
    setup.add_argument("--repo-id")
    setup.add_argument("--repo-class", choices=["client", "internal"], default="internal")
    setup.add_argument(
        "--add-and-enable-source",
        action="append",
        nargs=5,
        metavar=("LAYER", "SOURCE_ID", "URL", "COMMIT", "NAMESPACE"),
        help="Register a native-format git source and enable it in org, repo, or user.",
    )
    setup.add_argument("--sync", action="store_true")
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

    import_skills = subparsers.add_parser("bootstrap-import")
    import_skills.add_argument("--source", type=Path, default=Path.home() / ".agents" / "skills")
    import_skills.add_argument("--dest", required=True, type=Path)
    import_skills.add_argument("--source-type", choices=["user", "corp"], default="user")
    import_skills.add_argument("--namespace", default="local")
    import_skills.add_argument("--include-system", action="store_true")
    import_skills.set_defaults(func=cmd_import_skills)

    import_codex_skills = subparsers.add_parser("import-codex-skills")
    import_codex_skills.add_argument("--source", type=Path, default=Path.home() / ".agents" / "skills")
    import_codex_skills.add_argument("--dest", required=True, type=Path)
    import_codex_skills.add_argument("--source-type", choices=["user", "corp"], default="user")
    import_codex_skills.add_argument("--namespace", default="local")
    import_codex_skills.add_argument("--include-system", action="store_true")
    import_codex_skills.set_defaults(func=cmd_import_skills)

    register = subparsers.add_parser("register-repo")
    register.add_argument("--workspace", type=Path, default=Path.cwd())
    register.add_argument("--repo-id", required=True)
    register.add_argument("--repo-class", choices=["client", "internal"], default="internal")
    register.set_defaults(func=cmd_register_repo)

    add_source = subparsers.add_parser("add-source")
    add_source.add_argument("--layer", choices=["org", "repo", "user"], required=True)
    add_source.add_argument("--source-id", required=True)
    add_source.add_argument("--url", required=True)
    add_source.add_argument("--commit", required=True)
    add_source.add_argument("--namespace", required=True)
    add_source.add_argument("--repo-id")
    add_source.add_argument("--enable", action="store_true")
    add_source.set_defaults(func=cmd_add_source)

    promote = subparsers.add_parser("promote-skills")
    promote.add_argument("--from-layer", choices=["user", "org", "repo"], required=True)
    promote.add_argument("--to-layer", choices=["user", "org", "repo"], required=True)
    promote.add_argument("--skill-id", action="append", default=[])
    promote.add_argument("--all-imported", action="store_true")
    promote.add_argument("--from-repo-id")
    promote.add_argument("--to-repo-id")
    promote.set_defaults(func=cmd_promote_skills)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--workspace", type=Path, default=Path.cwd())
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def cmd_setup(args: argparse.Namespace) -> int:
    corp_repo = args.corp_repo.expanduser().resolve()
    user_override = args.user_overrides.expanduser().resolve()
    cache_root = (args.cache_root or (Path.home() / ".team-agents" / "cache")).expanduser().resolve()
    actions: list[str] = []
    workspace = args.workspace.expanduser().resolve() if args.workspace is not None else None
    if args.repo_id and workspace is None:
        raise TeamAgentsError("--repo-id requires --workspace")
    if args.sync and workspace is None:
        raise TeamAgentsError("--sync requires --workspace")
    if args.init_corp_if_missing and not (corp_repo / "org" / "config.toml").exists():
        init_corp_repo(corp_repo)
        actions.append(f"initialized corp repo at {corp_repo}")
    if args.init_user_if_missing and not (user_override / "config.toml").exists():
        init_user_overrides(user_override)
        actions.append(f"initialized user overrides at {user_override}")
    ensure_user_override_layout(user_override)
    config = MachineConfig(
        corp_repo_path=corp_repo,
        user_override_path=user_override,
        cache_root=cache_root,
        default_tool_target=args.tool_target,
    )
    path = write_machine_config(config)
    if workspace is not None and args.repo_id:
        config_path = register_repo(
            corp_root=corp_repo,
            workspace=workspace,
            repo_id=args.repo_id,
            repo_class=args.repo_class,
        )
        actions.append(f"registered workspace {workspace} as {args.repo_id} ({args.repo_class}) at {config_path}")
    if args.import_skills_from is not None:
        import_root, source_type, namespace = resolve_import_target(
            corp_repo=corp_repo,
            user_override=user_override,
            import_to=args.import_skills_to,
            repo_id=args.repo_id,
        )
        summary = import_folder_skills(
            source_root=args.import_skills_from.expanduser().resolve(),
            layer_root=import_root,
            source_type=source_type,
            namespace=namespace,
            include_system=args.include_system_skills,
        )
        actions.append(
            f"bootstrapped {summary['skills']} skills and {summary['docs']} docs from {args.import_skills_from.expanduser().resolve()} into {args.import_skills_to}"
        )
    for source_args in args.add_and_enable_source or []:
        layer, source_id, url, commit, namespace = source_args
        manifest_path = add_source(
            corp_repo=corp_repo,
            user_override=user_override,
            layer=layer,
            source_id=source_id,
            url=url,
            commit=commit,
            namespace=namespace,
            repo_id=args.repo_id,
            enable=True,
        )
        actions.append(f"registered source {source_id} for {layer} at {manifest_path}")
    if args.sync:
        corp = load_corp_repo(corp_repo)
        user = load_user_overrides(user_override)
        result = resolve_workspace(workspace, config, corp, user)
        written = write_sync_output(result)
        actions.append(f"synced {workspace} and wrote {len(written)} files")
    print(f"Wrote machine config to {path}")
    for action in actions:
        print(action)
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


def cmd_import_skills(args: argparse.Namespace) -> int:
    dest = args.dest.expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for name in ["skills", "policies", "docs", "sources", "workspaces"]:
        (dest / name).mkdir(parents=True, exist_ok=True)
    summary = import_folder_skills(
        source_root=args.source.expanduser().resolve(),
        layer_root=dest,
        source_type=args.source_type,
        namespace=args.namespace,
        include_system=args.include_system,
    )
    print(
        json.dumps(
            {
                "dest": str(dest),
                "source": str(args.source.expanduser().resolve()),
                "source_type": args.source_type,
                "namespace": args.namespace,
                "mode": "bootstrap-import",
                "imported_skills": summary["skills"],
                "imported_docs": summary["docs"],
                "include_system": args.include_system,
            },
            indent=2,
        )
    )
    return 0


def cmd_register_repo(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    config_path = register_repo(
        corp_root=machine_config.corp_repo_path,
        workspace=args.workspace.expanduser().resolve(),
        repo_id=args.repo_id,
        repo_class=args.repo_class,
    )
    print(
        json.dumps(
            {
                "workspace": str(args.workspace.expanduser().resolve()),
                "repo_id": args.repo_id,
                "repo_class": args.repo_class,
                "config_path": str(config_path),
            },
            indent=2,
        )
    )
    return 0


def cmd_add_source(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    manifest_path = add_source(
        corp_repo=machine_config.corp_repo_path,
        user_override=machine_config.user_override_path,
        layer=args.layer,
        source_id=args.source_id,
        url=args.url,
        commit=args.commit,
        namespace=args.namespace,
        repo_id=args.repo_id,
        enable=args.enable,
    )
    print(
        json.dumps(
            {
                "layer": args.layer,
                "source_id": args.source_id,
                "repo_id": args.repo_id,
                "manifest_path": str(manifest_path),
                "enabled": args.enable,
            },
            indent=2,
        )
    )
    return 0


def cmd_promote_skills(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    promoted = promote_skills(
        corp_root=machine_config.corp_repo_path,
        user_root=machine_config.user_override_path,
        from_layer=args.from_layer,
        to_layer=args.to_layer,
        skill_ids=[str(item) for item in args.skill_id],
        from_repo_id=args.from_repo_id,
        to_repo_id=args.to_repo_id,
        all_imported=args.all_imported,
    )
    print(
        json.dumps(
            {
                "from_layer": args.from_layer,
                "to_layer": args.to_layer,
                "from_repo_id": args.from_repo_id,
                "to_repo_id": args.to_repo_id,
                "promoted_skill_ids": promoted,
            },
            indent=2,
        )
    )
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


def resolve_import_target(
    corp_repo: Path,
    user_override: Path,
    import_to: str,
    repo_id: str | None,
) -> tuple[Path, str, str]:
    if import_to == "user":
        config = load_user_overrides(user_override).layer.config
        return user_override, "user", config.identifier
    if import_to == "org":
        config = load_corp_repo(corp_repo).org.config
        return corp_repo / "org", "corp", config.identifier
    if import_to == "repo":
        if not repo_id:
            raise TeamAgentsError("--import-skills-to repo requires --repo-id")
        corp = load_corp_repo(corp_repo)
        layer = corp.repos.get(repo_id)
        if layer is None:
            raise TeamAgentsError(f"Unknown repo id for import target: {repo_id}")
        return corp_repo / "repos" / repo_id, "corp", layer.config.identifier
    raise TeamAgentsError(f"Unsupported import target {import_to!r}")


def add_source(
    corp_repo: Path,
    user_override: Path,
    layer: str,
    source_id: str,
    url: str,
    commit: str,
    namespace: str,
    repo_id: str | None,
    enable: bool,
) -> Path:
    if layer == "user":
        manifest_path = register_user_source(user_override, source_id, url, commit, namespace)
    else:
        manifest_path = register_corp_source(corp_repo, source_id, url, commit, namespace)
    if enable:
        layer_root = resolve_layer_root(corp_repo, user_override, layer, repo_id=repo_id)
        enable_source_in_layer(layer_root, source_id)
    return manifest_path
