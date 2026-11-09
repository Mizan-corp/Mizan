"""mizan-server — install and manage Mizan on this computer.

    mizan-server install --licence KEY --admin-password PASS [--demo] [--json]
    mizan-server status [--json]
    mizan-server start | stop | restart
    mizan-server licence show | set KEY | check-in
    mizan-server backup [--to DIR] | backups | restore FILE
    mizan-server uninstall [--delete-data] --yes
    mizan-server run            (what the service runs)
    mizan-server version
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from mizan_server import engine, postgres, service
from mizan_server.layout import Config, version

STEP_LABELS = {
    "check": "Checking the licence and this computer",
    "prepare": "Preparing folders and settings",
    "database": "Setting up the database",
    "workspace": "Creating the workspace",
    "network": "Creating the network certificate",
    "service": "Registering the Mizan service",
    "start": "Starting Mizan",
    "done": "Done",
    "remove-service": "Stopping and removing the Mizan service",
    "data": "Removing data",
}


def _emitter(as_json: bool):
    def emit(step: str, status: str, **details) -> None:
        if as_json:
            print(json.dumps({"step": step, "status": status, **details}, ensure_ascii=False), flush=True)
            return
        mark = {"running": "…", "done": "✔", "skipped": "–", "error": "✘"}.get(status, "·")
        if status == "running":
            print(f"{mark} {STEP_LABELS.get(step, step)}", flush=True)
        elif step == "done":
            print(f"\n✔ Mizan is installed: {details.get('workspace')} ({details.get('mode')})")
            print(f"  Open: {details.get('url')}")
            for a in details.get("addresses") or []:
                print(f"  On the network: {a}")
            if details.get("ca_certificate"):
                print(f"  Tills: install the certificate {details['ca_certificate']} (or open the address and follow the link)")
            print(f"  Admin: {details.get('admin')}")
        elif status == "skipped":
            print(f"{mark} {STEP_LABELS.get(step, step)}: skipped" + (f" ({details['hint']})" if details.get("hint") else ""), flush=True)
        elif status == "done" and details:
            info = ", ".join(f"{k}={v}" for k, v in details.items() if isinstance(v, (str, int, bool)) and k != "hint")
            print(f"  {mark} {info}" if info else f"  {mark}", flush=True)
            if details.get("hint"):
                print(f"    {details['hint']}")

    return emit


def _app_env(cfg: Config) -> None:
    from mizan_server.runner import load_app_environment

    load_app_environment(cfg)


# ─── Commands ──────────────────────────────────────────────────────────────


def cmd_install(a) -> int:
    emit = _emitter(a.json)
    key = a.licence or (Path(a.licence_file).read_text().strip() if a.licence_file else "")
    password = a.admin_password or os.environ.get("MIZAN_ADMIN_PASSWORD", "")
    try:
        engine.install(
            licence_key=key, admin_password=password, emit=emit, admin_username=a.admin_username, admin_name=a.admin_name,
            data_dir=Path(a.data_dir) if a.data_dir else None, port=a.port, demo=a.demo, cloud_url=a.cloud_url,
            app_env=a.app_env, with_service=not a.no_service, licence_public_key=a.licence_public_key or "",
        )
        return 0
    except engine.InstallError as e:
        if a.json:
            print(json.dumps({"step": e.step, "status": "error", "message": str(e)}, ensure_ascii=False), flush=True)
        else:
            print(f"✘ {STEP_LABELS.get(e.step, e.step)}: {e}", file=sys.stderr)
        return 1


def cmd_setup_workspace(a) -> int:
    """Internal: the workspace step, run with the app's environment."""
    from mizan_server.runner import app_import_path

    app_import_path()
    from app.onprem.setup import main as setup_main

    args = ["--licence", a.licence, "--admin-password", a.admin_password]
    if a.admin_username:
        args += ["--admin-username", a.admin_username]
    if a.admin_name:
        args += ["--admin-name", a.admin_name]
    if a.demo:
        args.append("--demo")
    return setup_main(args)


def cmd_run(a) -> int:
    from mizan_server.runner import run

    return run(Config.load(Path(a.data_dir) if a.data_dir else None))


def cmd_status(a) -> int:
    try:
        cfg = Config.load(Path(a.data_dir) if a.data_dir else None)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 3
    info = {
        "version": version(),
        "mode": cfg.mode,
        "url": cfg.url,
        "service_running": service.control(cfg, "status"),
        "database_running": postgres.running(cfg),
        "data_dir": str(cfg.data),
    }
    try:
        _app_env(cfg)
        from app.onprem import licence

        lic = licence.current()
        info["licence"] = {k: lic.get(k) for k in ("status", "valid_until", "days_left")}
        info["workspace"] = ((lic.get("payload") or {}).get("workspace") or {}).get("name")
    except Exception as e:  # status must work even if the app can't load
        info["licence"] = {"status": "unknown", "error": str(e)[:200]}
    from mizan_server.backup import list_backups

    latest = list_backups(cfg)
    info["last_backup"] = latest[0].name if latest else None
    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        for k, v in info.items():
            print(f"{k:>17}: {v}")
    return 0


def cmd_control(a) -> int:
    cfg = Config.load(Path(a.data_dir) if a.data_dir else None)
    ok = service.control(cfg, a.command)
    print(("✔ " if ok else "✘ ") + a.command)
    return 0 if ok else 1


def cmd_licence(a) -> int:
    cfg = Config.load(Path(a.data_dir) if a.data_dir else None)
    _app_env(cfg)
    from app.core import licensing
    from app.onprem import checkin, licence

    if a.action == "show":
        lic = licence.current()
        print(json.dumps({k: lic.get(k) for k in ("status", "valid_until", "days_left")}, ensure_ascii=False))
        return 0
    if a.action == "set":
        try:
            payload = licence.accept_key(a.key)
        except licensing.LicenceError as e:
            print(f"✘ {e}", file=sys.stderr)
            return 1
        print(f"✔ Licence valid until {payload['valid_until']}")
        return 0
    import asyncio

    result = asyncio.run(checkin.check_in_once())
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_backup(a) -> int:
    from mizan_server.backup import list_backups, restore_backup, run_backup

    cfg = Config.load(Path(a.data_dir) if a.data_dir else None)
    if a.command == "backups":
        for p in list_backups(cfg):
            print(f"{p.name}  {p.stat().st_size // 1024} KB")
        return 0
    if a.command == "restore":
        was_running = service.control(cfg, "status")
        if was_running:
            service.control(cfg, "stop")
        try:
            restore_backup(cfg, Path(a.file))
        finally:
            if was_running:
                service.control(cfg, "start")
        print(f"✔ Restored {a.file}")
        return 0
    path = run_backup(cfg, Path(a.to) if a.to else None)
    print(f"✔ {path}")
    return 0


def cmd_uninstall(a) -> int:
    if not a.yes:
        print("Add --yes to confirm." + (" This also DELETES all data." if a.delete_data else " Data is kept."), file=sys.stderr)
        return 2
    engine.uninstall(delete_data=a.delete_data, emit=_emitter(a.json), data_dir=Path(a.data_dir) if a.data_dir else None)
    return 0


def cmd_verify_licence(a) -> int:
    """Internal: verify a key's signature with the app's rules."""
    from mizan_server.runner import app_import_path

    app_import_path()
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@127.0.0.1/x")
    os.environ.setdefault("SECRET_KEY", "verify-only")
    from app.core import licensing

    try:
        print(json.dumps({"ok": True, "payload": licensing.verify(a.key)}, ensure_ascii=False))
        return 0
    except licensing.LicenceError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1


def main(argv: list[str] | None = None) -> int:
    if os.name == "nt" and getattr(sys, "frozen", False):
        # Don't let programs started from here (PostgreSQL) inherit the packaged
        # Python's DLL folder: they must load their own DLLs.
        import ctypes

        ctypes.windll.kernel32.SetDllDirectoryW(None)
    # Windows pipes default to the ANSI code page; progress has Arabic names and ✔.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="mizan-server", description="Install and manage Mizan on this computer.")
    p.add_argument("--data-dir", help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True)

    i = sub.add_parser("install", help="install (or repair) Mizan with a licence key")
    i.add_argument("--licence", help="the licence key from the owner panel")
    i.add_argument("--licence-file", help="a .mzn licence file")
    i.add_argument("--admin-password", help="or set MIZAN_ADMIN_PASSWORD")
    i.add_argument("--admin-username")
    i.add_argument("--admin-name")
    i.add_argument("--port", type=int)
    i.add_argument("--demo", action="store_true", help="fill with sample data")
    i.add_argument("--no-service", action="store_true", help="don't register a background service")
    i.add_argument("--cloud-url", help=argparse.SUPPRESS)
    i.add_argument("--app-env", default="production", help=argparse.SUPPRESS)
    i.add_argument("--licence-public-key", help=argparse.SUPPRESS)
    i.add_argument("--json", action="store_true", help="progress as JSON lines (for Mizan Setup)")
    i.set_defaults(func=cmd_install)

    w = sub.add_parser("setup-workspace", help=argparse.SUPPRESS)
    for flag in ("--licence", "--admin-password"):
        w.add_argument(flag, required=True)
    w.add_argument("--admin-username")
    w.add_argument("--admin-name")
    w.add_argument("--demo", action="store_true")
    w.set_defaults(func=cmd_setup_workspace)

    v = sub.add_parser("verify-licence", help=argparse.SUPPRESS)
    v.add_argument("key")
    v.set_defaults(func=cmd_verify_licence)

    sub.add_parser("run", help="run Mizan in the foreground (what the service runs)").set_defaults(func=cmd_run)
    s = sub.add_parser("status", help="what's installed and running")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_status)
    for name in ("start", "stop", "restart"):
        sub.add_parser(name, help=f"{name} the Mizan service").set_defaults(func=cmd_control)

    lic = sub.add_parser("licence", help="show, set or renew the licence")
    lic_sub = lic.add_subparsers(dest="action", required=True)
    lic_sub.add_parser("show")
    lic_set = lic_sub.add_parser("set")
    lic_set.add_argument("key")
    lic_sub.add_parser("check-in")
    lic.set_defaults(func=cmd_licence)

    b = sub.add_parser("backup", help="back up the database now")
    b.add_argument("--to", help="also copy the backup to this folder")
    b.set_defaults(func=cmd_backup)
    sub.add_parser("backups", help="list backups").set_defaults(func=cmd_backup)
    r = sub.add_parser("restore", help="restore a backup (the current data is backed up first)")
    r.add_argument("file")
    r.set_defaults(func=cmd_backup)

    u = sub.add_parser("uninstall", help="remove the service (and, with --delete-data, all data)")
    u.add_argument("--delete-data", action="store_true")
    u.add_argument("--yes", action="store_true")
    u.add_argument("--json", action="store_true")
    u.set_defaults(func=cmd_uninstall)

    sub.add_parser("version").set_defaults(func=lambda a: print(version()) or 0)

    args = p.parse_args(argv)
    return args.func(args) or 0
