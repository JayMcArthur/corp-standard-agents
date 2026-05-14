from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from team_agents.doctor import doctor_json, doctor_text, run_doctor
from team_agents.errors import TeamAgentsError
from team_agents.importers import import_folder_skills
from team_agents.lifecycle import migrate_user_overrides, record_recent_workspace, reseed, run_update
from team_agents.loaders import load_corp_repo, load_user_overrides
from team_agents.machine import ensure_user_override_layout, load_machine_config, write_machine_config
from team_agents.models import CorpRepo, Item, MachineConfig, ResolutionResult, UserOverrides
from team_agents.output import write_sync_output
from team_agents.promotion import promote_skills
from team_agents.repo_registry import register_repo
from team_agents.resolution import resolve_workspace
from team_agents.scaffold import init_corp_repo, init_user_overrides, init_user_profile
from team_agents.source_registry import enable_source_in_layer, register_corp_source, register_user_source, resolve_layer_root
from team_agents.toml_utils import read_toml, write_toml_document


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
    setup.add_argument("--user-overrides", type=Path)
    setup.add_argument("--user")
    setup.add_argument("--cache-root", type=Path)
    setup.add_argument("--tool-target", choices=["all", "codex", "claude", "cursor"], default="all")
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

    audit = subparsers.add_parser("audit")
    audit.add_argument("--workspace", type=Path, default=Path.cwd())
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(func=cmd_audit)

    context = subparsers.add_parser("context")
    context.add_argument("--workspace", type=Path, default=Path.cwd())
    context.add_argument("--pretty", action="store_true")
    context.set_defaults(func=cmd_context)

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

    onboard = subparsers.add_parser("onboard-repo")
    onboard.add_argument("--workspace", type=Path, default=Path.cwd())
    onboard.add_argument("--repo-id")
    onboard.add_argument("--repo-class", choices=["client", "internal"])
    onboard.add_argument("--repo-group-id")
    onboard.add_argument("--enable-skill", action="append", default=[])
    onboard.add_argument("--enable-policy", action="append", default=[])
    onboard.add_argument("--enable-doc", action="append", default=[])
    onboard.add_argument("--recommended-agent-type", action="append", default=[])
    onboard.add_argument("--no-sync", action="store_true")
    onboard.add_argument("--json", action="store_true")
    onboard.set_defaults(func=cmd_onboard_repo)

    bind_workspace = subparsers.add_parser("bind-workspace")
    bind_workspace.add_argument("--path", type=Path, default=Path.cwd())
    bind_workspace.add_argument("--name")
    bind_workspace.add_argument("--repo-id")
    bind_workspace.add_argument("--repo-group-id")
    bind_workspace.add_argument("--no-sync", action="store_true")
    bind_workspace.add_argument("--json", action="store_true")
    bind_workspace.set_defaults(func=cmd_bind_workspace)

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

    refresh = subparsers.add_parser("refresh-personal-skills")
    refresh.add_argument("--source", type=Path, default=Path.home() / ".agents" / "skills")
    refresh.add_argument("--include-system", action="store_true")
    refresh.add_argument("--json", action="store_true")
    refresh.set_defaults(func=cmd_refresh_personal_skills)

    migrate = subparsers.add_parser("migrate-user-overrides")
    migrate.add_argument("--user", required=True)
    migrate.add_argument("--corp-repo", required=True, type=Path)
    migrate.add_argument("--legacy-root", type=Path, default=Path.home() / ".team-agents-user")
    migrate.add_argument("--cache-root", type=Path, default=Path.home() / ".team-agents" / "cache")
    migrate.add_argument("--json", action="store_true")
    migrate.set_defaults(func=cmd_migrate_user_overrides)

    update = subparsers.add_parser("update")
    update.add_argument("--json", action="store_true")
    update.set_defaults(func=cmd_update)

    return parser


def cmd_setup(args: argparse.Namespace) -> int:
    corp_repo = args.corp_repo.expanduser().resolve()
    user_override = resolve_setup_user_root(corp_repo=corp_repo, user_overrides=args.user_overrides, user_name=args.user)
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
    ensure_setup_user_root(corp_repo=corp_repo, user_root=user_override, user_name=args.user, init_if_missing=args.init_user_if_missing)
    if args.user is None:
        ensure_user_override_layout(user_override)
    config = MachineConfig(
        corp_repo_path=corp_repo,
        user_override_path=user_override,
        cache_root=cache_root,
        default_tool_target=args.tool_target,
        user_name=args.user,
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
            replace_existing=True,
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
    corp = load_corp_repo(corp_repo)
    user = load_user_overrides(user_override)
    reseed_summary = reseed(
        config,
        corp,
        user,
        workspaces=[workspace] if args.sync and workspace is not None else None,
        include_recent_workspaces=not args.sync,
    )
    global_written = reseed_summary["global_written"]
    if global_written:
        actions.append(f"seeded {len(global_written)} user-global tool output(s)")
    if args.sync and workspace is not None:
        synced = reseed_summary["workspaces"]
        written = synced[0]["written"] if synced else []
        actions.append(f"synced {workspace} and wrote {len(written)} files")
    print(f"Wrote machine config to {path}")
    for action in actions:
        print(action)
    return 0


def resolve_setup_user_root(corp_repo: Path, user_overrides: Path | None, user_name: str | None) -> Path:
    if user_name and user_overrides:
        raise TeamAgentsError("setup accepts either --user or --user-overrides, not both")
    if user_name:
        return (corp_repo / "users" / user_name).resolve()
    if user_overrides is None:
        raise TeamAgentsError("setup requires either --user or --user-overrides")
    return user_overrides.expanduser().resolve()


def ensure_setup_user_root(corp_repo: Path, user_root: Path, user_name: str | None, init_if_missing: bool) -> None:
    if (user_root / "config.toml").exists():
        return
    if user_name is not None:
        (corp_repo / "users").mkdir(parents=True, exist_ok=True)
        init_user_profile(user_root, user_name)
        return
    if init_if_missing:
        init_user_overrides(user_root)
        return
    raise TeamAgentsError(f"User profile path does not exist: {user_root}")


def cmd_sync(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    corp = load_corp_repo(machine_config.corp_repo_path)
    user = load_user_overrides(machine_config.user_override_path)
    result = resolve_workspace(args.workspace, machine_config, corp, user)
    if args.dry_run:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0
    written = write_sync_output(result)
    record_recent_workspace(machine_config, args.workspace.expanduser().resolve())
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


def cmd_audit(args: argparse.Namespace) -> int:
    result = load_resolution_for_workspace(args.workspace)
    report = build_audit_report(result)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(audit_text(report))
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    result = load_resolution_for_workspace(args.workspace)
    payload = result.to_dict()
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))
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


def cmd_onboard_repo(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    corp = load_corp_repo(machine_config.corp_repo_path)
    workspace = args.workspace.expanduser().resolve()
    normalized_remotes = build_workspace_context_for_onboard(workspace, corp)
    repo_id, repo_class, repo_group_id, enabled_skills, optional_policies, docs, recommended_agent_types = resolve_onboard_inputs(
        args=args,
        corp=corp,
        workspace=workspace,
        normalized_remotes=normalized_remotes,
    )
    config_path = register_repo(
        corp_root=machine_config.corp_repo_path,
        workspace=workspace,
        repo_id=repo_id,
        repo_class=repo_class,
        repo_group_id=repo_group_id,
        enabled_skills=enabled_skills or None,
        optional_policies=optional_policies or None,
        docs=docs or None,
        recommended_agent_types=recommended_agent_types or None,
    )
    synced = False
    written: list[str] = []
    corp = load_corp_repo(machine_config.corp_repo_path)
    user = load_user_overrides(machine_config.user_override_path)
    if not args.no_sync:
        summary = reseed(machine_config, corp, user, workspaces=[workspace], include_recent_workspaces=False)
        synced_workspace = next((item for item in summary["workspaces"] if item["workspace"] == str(workspace)), None)
        written = list(synced_workspace["written"]) if synced_workspace else []
        synced = True
    else:
        reseed(machine_config, corp, user)
    payload = {
        "workspace": str(workspace),
        "repo_id": repo_id,
        "repo_class": repo_class,
        "repo_group_id": repo_group_id,
        "config_path": str(config_path),
        "enabled_skills": enabled_skills,
        "optional_policies": optional_policies,
        "docs": docs,
        "recommended_agent_types": recommended_agent_types,
        "synced": synced,
        "written": written,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2))
    return 0


def cmd_bind_workspace(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    corp = load_corp_repo(machine_config.corp_repo_path)
    user_root = machine_config.user_override_path
    config_path = user_root / "config.toml"
    data = read_toml(config_path)
    bindings = data.get("workspace_binding", [])
    if bindings is None:
        bindings = []
    if not isinstance(bindings, list):
        raise TeamAgentsError(f"workspace_binding must be a list in {config_path}")
    path = args.path.expanduser().resolve()
    name, repo_id, repo_group_id = resolve_bind_workspace_inputs(args=args, corp=corp, path=path)
    filtered = [entry for entry in bindings if Path(str(entry.get("path", ""))).expanduser().resolve() != path]
    record = {"name": name, "path": str(path)}
    if repo_id:
        record["repo_id"] = repo_id
    if repo_group_id:
        record["repo_group_id"] = repo_group_id
    filtered.append(record)
    data["workspace_binding"] = filtered
    write_toml_document(config_path, data)
    payload = {
        "config_path": str(config_path),
        "name": name,
        "path": str(path),
        "repo_id": repo_id,
        "repo_group_id": repo_group_id,
        "synced": False,
        "written": [],
    }
    user = load_user_overrides(user_root)
    if not args.no_sync:
        summary = reseed(machine_config, corp, user, workspaces=[path], include_recent_workspaces=False)
        synced_workspace = next((item for item in summary["workspaces"] if item["workspace"] == str(path)), None)
        payload["written"] = list(synced_workspace["written"]) if synced_workspace else []
        payload["synced"] = True
    else:
        reseed(machine_config, corp, user)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2))
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
    corp = load_corp_repo(machine_config.corp_repo_path)
    user = load_user_overrides(machine_config.user_override_path)
    reseed(machine_config, corp, user)
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
    corp = load_corp_repo(machine_config.corp_repo_path)
    user = load_user_overrides(machine_config.user_override_path)
    reseed(machine_config, corp, user)
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


def cmd_refresh_personal_skills(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    user_override = machine_config.user_override_path
    corp_repo = machine_config.corp_repo_path
    import_root, source_type, namespace = resolve_import_target(
        corp_repo=corp_repo,
        user_override=user_override,
        import_to="user",
        repo_id=None,
    )
    summary = import_folder_skills(
        source_root=args.source.expanduser().resolve(),
        layer_root=import_root,
        source_type=source_type,
        namespace=namespace,
        include_system=args.include_system,
        replace_existing=True,
    )
    corp = load_corp_repo(corp_repo)
    user = load_user_overrides(user_override)
    reseed(machine_config, corp, user)
    payload = {
        "source": str(args.source.expanduser().resolve()),
        "dest": str(import_root),
        "source_type": source_type,
        "namespace": namespace,
        "imported_skills": summary["skills"],
        "imported_docs": summary["docs"],
        "include_system": args.include_system,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2))
    return 0


def cmd_migrate_user_overrides(args: argparse.Namespace) -> int:
    report = migrate_user_overrides(
        legacy_root=args.legacy_root,
        corp_root=args.corp_repo.expanduser().resolve(),
        user_name=args.user,
        cache_root=args.cache_root.expanduser().resolve(),
    )
    corp = load_corp_repo(args.corp_repo.expanduser().resolve())
    user_root = (args.corp_repo.expanduser().resolve() / "users" / args.user).resolve()
    user = load_user_overrides(user_root)
    machine_config = MachineConfig(
        corp_repo_path=args.corp_repo.expanduser().resolve(),
        user_override_path=user_root,
        cache_root=args.cache_root.expanduser().resolve(),
        default_tool_target="all",
        user_name=args.user,
    )
    reseed(machine_config, corp, user)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, indent=2))
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    machine_config = load_machine_config()
    payload = run_update(machine_config)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2))
    return 0


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


def load_resolution_for_workspace(workspace: Path) -> ResolutionResult:
    machine_config = load_machine_config()
    corp = load_corp_repo(machine_config.corp_repo_path)
    user = load_user_overrides(machine_config.user_override_path)
    return resolve_workspace(workspace, machine_config, corp, user)


def build_audit_report(result: ResolutionResult) -> dict[str, object]:
    payload = result.to_dict()
    payload["active_items"] = {
        item_id: {
            "kind": resolved.item.kind,
            "title": resolved.item.title,
            "layer_name": resolved.layer_name,
            "status": resolved.status,
            "privacy": resolved.item.privacy,
            "source_ref": resolved.item.source_ref,
            "source_type": resolved.item.source_type,
            "source_namespace": resolved.item.source_namespace,
            "overridden_by": resolved.overridden_by,
            "replaced_from": resolved.replaced_from,
        }
        for item_id, resolved in sorted(result.items.items())
    }
    return payload


def audit_text(report: dict[str, object]) -> str:
    lines = [
        f"workspace: {report['workspace']}",
        f"matched-repo: {report['matched_repo_id'] or 'unknown'}",
        f"matched-repo-group: {report['matched_repo_group_id'] or 'none'}",
        f"repo-class: {report['repo_class']}",
        f"sources: {', '.join(report['enabled_sources']) or 'none'}",
        f"skills: {', '.join(report['enabled_skills']) or 'none'}",
        f"policies: {', '.join(report['active_policies']) or 'none'}",
        f"docs: {', '.join(report['active_docs']) or 'none'}",
        f"recommended-agent-types: {', '.join(report['recommended_agent_types']) or 'none'}",
        "",
        "items:",
    ]
    for item_id, item in report["active_items"].items():
        origin = item["replaced_from"]["id"] if item["replaced_from"] else item["source_ref"]
        lines.append(
            f"- {item_id}: {item['kind']} {item['status']} via {item['layer_name']} from {origin}"
        )
    denied = report.get("denied_items", {})
    if denied:
        lines.append("")
        lines.append("denied-items:")
        for item_id, item in denied.items():
            reason = item.get("denied_reason") or "disabled or denied"
            lines.append(f"- {item_id}: {reason}")
    warnings = report.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("warnings:")
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def build_workspace_context_for_onboard(workspace: Path, corp: CorpRepo) -> list[str]:
    from team_agents.git_tools import find_git_root, list_normalized_remotes

    git_root = find_git_root(workspace)
    if git_root is None:
        raise TeamAgentsError(f"Workspace is not inside a git repo: {workspace}")
    normalized_remotes = list_normalized_remotes(git_root)
    if not normalized_remotes:
        raise TeamAgentsError(f"Workspace git repo has no remotes: {git_root}")
    matching = [repo_id for repo_id, layer in corp.repos.items() if set(normalized_remotes).intersection(layer.config.normalized_remotes)]
    if matching:
        raise TeamAgentsError(f"Workspace already matches configured repo id(s): {', '.join(sorted(matching))}")
    return normalized_remotes


def derive_repo_id(normalized_remotes: list[str], workspace: Path) -> str:
    if normalized_remotes:
        candidate = normalized_remotes[0].split("/")[-1]
    else:
        candidate = workspace.name
    slug = re.sub(r"[^a-z0-9_-]+", "-", candidate.lower()).strip("-")
    return slug or "repo"


def unique_list(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def resolve_onboard_inputs(
    *,
    args: argparse.Namespace,
    corp: CorpRepo,
    workspace: Path,
    normalized_remotes: list[str],
) -> tuple[str, str, str | None, list[str], list[str], list[str], list[str]]:
    guided = args.repo_id is None or args.repo_class is None or args.repo_group_id is None
    repo_id = args.repo_id or prompt_repo_id(normalized_remotes, workspace)
    repo_class = args.repo_class or prompt_repo_class()
    repo_group_id = args.repo_group_id
    if repo_group_id is None:
        repo_group_id = prompt_repo_group_id(corp)
    validate_repo_group_id(repo_group_id, corp)
    enabled_skills = unique_list(args.enable_skill)
    optional_policies = unique_list(args.enable_policy)
    docs = unique_list(args.enable_doc)
    recommended_agent_types = unique_list(args.recommended_agent_type)
    if guided:
        enabled_skills = enabled_skills or prompt_item_selection("skills", collect_kind_ids(corp, "skill"))
        optional_policies = optional_policies or prompt_item_selection("optional policies", collect_kind_ids(corp, "policy"))
        docs = docs or prompt_item_selection("docs", collect_kind_ids(corp, "doc"))
        recommended_agent_types = recommended_agent_types or prompt_agent_types(corp)
    return repo_id, repo_class, repo_group_id, enabled_skills, optional_policies, docs, recommended_agent_types


def prompt_repo_id(normalized_remotes: list[str], workspace: Path) -> str:
    default = derive_repo_id(normalized_remotes, workspace)
    value = input(f"Repo id [{default}]: ").strip()
    return value or default


def prompt_repo_class() -> str:
    default = "internal"
    while True:
        value = input(f"Repo class (internal/client) [{default}]: ").strip().lower()
        if not value:
            return default
        if value in {"internal", "client"}:
            return value
        print("Enter 'internal' or 'client'.", file=sys.stderr)


def prompt_repo_group_id(corp: CorpRepo) -> str | None:
    if not corp.repo_groups:
        return None
    print("Available repo groups:", file=sys.stderr)
    for repo_group_id in sorted(corp.repo_groups):
        print(f"- {repo_group_id}", file=sys.stderr)
    value = input("Repo group id [none]: ").strip()
    return value or None


def validate_repo_group_id(repo_group_id: str | None, corp: CorpRepo) -> None:
    if repo_group_id and repo_group_id not in corp.repo_groups:
        raise TeamAgentsError(f"Unknown repo-group id: {repo_group_id}")


def collect_kind_ids(corp: CorpRepo, kind: str) -> list[str]:
    item_ids: list[str] = []
    for layer in [corp.org, *corp.repo_groups.values(), *corp.repos.values()]:
        for item_id, item in sorted(layer.items.items()):
            if item.kind == kind and item_id not in item_ids:
                item_ids.append(item_id)
    return item_ids


def prompt_item_selection(label: str, options: list[str]) -> list[str]:
    if not options:
        return []
    print(f"Available {label}:", file=sys.stderr)
    for option in options:
        print(f"- {option}", file=sys.stderr)
    raw = input(f"Comma-separated {label} [none]: ").strip()
    if not raw:
        return []
    selected = unique_list([item.strip() for item in raw.split(",") if item.strip()])
    unknown = [item for item in selected if item not in options]
    if unknown:
        raise TeamAgentsError(f"Unknown {label}: {', '.join(unknown)}")
    return selected


def prompt_agent_types(corp: CorpRepo) -> list[str]:
    values: list[str] = []
    for layer in [corp.org, *corp.repo_groups.values(), *corp.repos.values()]:
        for agent_type in layer.config.recommended_agent_types:
            if agent_type not in values:
                values.append(agent_type)
    if not values:
        return []
    print("Available recommended agent types:", file=sys.stderr)
    for value in values:
        print(f"- {value}", file=sys.stderr)
    raw = input("Comma-separated recommended agent types [none]: ").strip()
    if not raw:
        return []
    selected = unique_list([item.strip() for item in raw.split(",") if item.strip()])
    unknown = [item for item in selected if item not in values]
    if unknown:
        raise TeamAgentsError(f"Unknown recommended agent types: {', '.join(unknown)}")
    return selected


def resolve_bind_workspace_inputs(
    *,
    args: argparse.Namespace,
    corp: CorpRepo,
    path: Path,
) -> tuple[str, str | None, str | None]:
    name = args.name or prompt_workspace_name(path)
    repo_id = args.repo_id
    repo_group_id = args.repo_group_id
    if bool(repo_id) == bool(repo_group_id):
        repo_id, repo_group_id = prompt_workspace_target(corp)
    validate_bind_target(repo_id, repo_group_id, corp)
    return name, repo_id, repo_group_id


def prompt_workspace_name(path: Path) -> str:
    default = path.name
    value = input(f"Workspace binding name [{default}]: ").strip()
    return value or default


def prompt_workspace_target(corp: CorpRepo) -> tuple[str | None, str | None]:
    print("Bind workspace to a repo or repo-group.", file=sys.stderr)
    while True:
        target_kind = input("Target kind (repo/repo-group) [repo-group]: ").strip().lower()
        if not target_kind:
            target_kind = "repo-group"
        if target_kind in {"repo", "repo-group"}:
            break
        print("Enter 'repo' or 'repo-group'.", file=sys.stderr)
    if target_kind == "repo":
        print("Available repos:", file=sys.stderr)
        for repo_id in sorted(corp.repos):
            print(f"- {repo_id}", file=sys.stderr)
        repo_id = input("Repo id: ").strip()
        return repo_id or None, None
    print("Available repo groups:", file=sys.stderr)
    for repo_group_id in sorted(corp.repo_groups):
        print(f"- {repo_group_id}", file=sys.stderr)
    repo_group_id = input("Repo group id: ").strip()
    return None, repo_group_id or None


def validate_bind_target(repo_id: str | None, repo_group_id: str | None, corp: CorpRepo) -> None:
    if bool(repo_id) == bool(repo_group_id):
        raise TeamAgentsError("bind-workspace requires exactly one of --repo-id or --repo-group-id")
    if repo_id and repo_id not in corp.repos:
        raise TeamAgentsError(f"Unknown repo id: {repo_id}")
    if repo_group_id and repo_group_id not in corp.repo_groups:
        raise TeamAgentsError(f"Unknown repo-group id: {repo_group_id}")
