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
    key = a.licence or (Path(a.licence_file).read_text(encoding="utf-8").strip() if a.licence_file else "")
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
    try:
        from app.onprem import state

        st = state.read_state()
        info["backup_copy_to"] = cfg.backup_copy_to or None
        if st.get("backup_copy_error"):
            info["backup_copy_error"] = st["backup_copy_error"]
        info["update_available"] = (st.get("update_available") or {}).get("version")
        info["last_update"] = st.get("last_update")
    except Exception:
        pass
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
    from app.platform.licensing import keys as licensing
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


def cmd_update(a) -> int:
    """Update to the release Mizan Cloud offered (see update.py)."""
    import asyncio
    import time

    from mizan_server import update

    cfg = Config.load(Path(a.data_dir) if a.data_dir else None)
    _app_env(cfg)
    from app.onprem import checkin, state

    if a.check:
        result = asyncio.run(checkin.check_in_once())
        if not result.get("ok"):
            print(f"✘ Couldn't reach Mizan Cloud ({result.get('reason')}).", file=sys.stderr)
            return 1
    try:
        release = update.offered_release()
    except update.UpdateError as e:
        print(f"✘ {e}", file=sys.stderr)
        return 1
    if not release:
        print(f"✔ Up to date ({version()})." + ("" if a.check else " Add --check to ask Mizan Cloud now."))
        return 0
    print(f"Mizan {release['version']} is available (installed: {version()}).")
    if release.get("notes"):
        print(release["notes"])
    if a.check_only:
        return 0
    shifts = update.open_shifts(cfg)
    if shifts and not a.force:
        print(f"✘ {shifts} till shift(s) are open. Close them first, or add --force to update anyway.", file=sys.stderr)
        return 3
    if not a.yes:
        if not sys.stdin.isatty():
            print("Add --yes to confirm.", file=sys.stderr)
            return 2
        answer = input("Mizan stops for a few minutes while it updates. Continue? [y/N] ").strip().lower()
        if answer not in ("y", "yes", "نعم"):
            return 2
    try:
        archive = update.download(cfg, release)
        staged = update.stage(cfg, archive, release)
    except (update.UpdateError, OSError) as e:
        print(f"✘ {e}", file=sys.stderr)
        return 1
    backup = update.backup_now(cfg)
    print(f"✔ Backed up the database: {backup.name}")
    before = (state.read_state().get("last_update") or {}).get("at")
    update.launch_apply(cfg, staged, backup)
    print("… Updating (the service restarts). Log: " + str(cfg.data / "logs" / "update.log"))
    if update.IS_WINDOWS:
        # This program runs from the folder being replaced: leave so it can be moved.
        print("Check the result in a few minutes with: mizan-server status")
        return 0
    deadline = time.time() + 20 * 60
    while time.time() < deadline:
        time.sleep(3)
        last = state.read_state().get("last_update") or {}
        if last.get("at") and last.get("at") != before:
            if last.get("ok"):
                print(f"✔ Updated to {last.get('to')}.")
                return 0
            print(f"✘ The update didn't go through; {last.get('from')} is running again. {last.get('error') or ''}", file=sys.stderr)
            return 1
    print("… Still updating; check later with: mizan-server status", file=sys.stderr)
    return 1


def cmd_apply_update(a) -> int:
    """Internal: run from the unpacked release, replaces the installed program (update.py)."""
    from mizan_server import update

    cfg = Config.load(Path(a.data_dir) if a.data_dir else None)
    _app_env(cfg)
    if a.wait_pid:
        update.wait_for_exit(a.wait_pid)
    return 0 if update.apply(cfg, Path(a.source), Path(a.backup)) else 1


def cmd_backup_to(a) -> int:
    """Where every backup is also copied (#90): a USB drive, another disk or a network share."""
    cfg = Config.load(Path(a.data_dir) if a.data_dir else None)
    if a.off:
        cfg.backup_copy_to = ""
        cfg.save()
        print("✔ Backups are kept only in " + str(cfg.data / "backups"))
        return 0
    if not a.path:
        print(cfg.backup_copy_to or "(not set)")
        return 0
    target = Path(a.path).expanduser().resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".mizan-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        print(f"✘ Can't write to {target}: {e}", file=sys.stderr)
        return 1
    cfg.backup_copy_to = str(target)
    cfg.save()
    if cfg.run_as:
        import subprocess

        subprocess.run(["chown", f"{cfg.run_as}:{cfg.run_as}", str(target)], check=False)
    print(f"✔ Every backup is now also copied to {target} (the newest 14 kept there).")
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
    from app.platform.licensing import keys as licensing

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
    bt = sub.add_parser("backup-to", help="also copy every backup to a folder (USB, network share); --off to stop")
    bt.add_argument("path", nargs="?")
    bt.add_argument("--off", action="store_true")
    bt.set_defaults(func=cmd_backup_to)
    r = sub.add_parser("restore", help="restore a backup (the current data is backed up first)")
    r.add_argument("file")
    r.set_defaults(func=cmd_backup)

    u = sub.add_parser("uninstall", help="remove the service (and, with --delete-data, all data)")
    u.add_argument("--delete-data", action="store_true")
    u.add_argument("--yes", action="store_true")
    u.add_argument("--json", action="store_true")
    u.set_defaults(func=cmd_uninstall)

    up = sub.add_parser("update", help="update to the newest release (backs up first, rolls back on failure)")
    up.add_argument("--check", action="store_true", help="ask Mizan Cloud now instead of using the last check-in")
    up.add_argument("--check-only", action="store_true", help="only say whether an update is available")
    up.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    up.add_argument("--force", action="store_true", help="update even while till shifts are open")
    up.set_defaults(func=cmd_update)
    ap = sub.add_parser("apply-update", help=argparse.SUPPRESS)
    ap.add_argument("--from", dest="source", required=True)
    ap.add_argument("--backup", required=True)
    ap.add_argument("--wait-pid", type=int, default=0)
    ap.set_defaults(func=cmd_apply_update)

    sub.add_parser("version").set_defaults(func=lambda a: print(version()) or 0)

    args = p.parse_args(argv)
    return args.func(args) or 0
