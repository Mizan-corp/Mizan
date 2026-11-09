"""The install engine: the same steps for Mizan Setup's wizard and for the command line.

Each step reports progress through `emit(step, status, **details)`; the wizard
shows it, the command line prints it (or JSON lines with --json). Running it
again on an installed computer repairs or updates: it reuses the existing
configuration, database and workspace.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from mizan_server import postgres, service
from mizan_server.layout import IS_WINDOWS, Config, default_data_dir, install_root, is_admin

Emit = Callable[..., None]

STEPS = ["check", "prepare", "database", "workspace", "network", "service", "start", "done"]


class InstallError(RuntimeError):
    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step


def self_command() -> list[str]:
    """How to run this program again (frozen build or from source)."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "mizan_server"]


def peek_licence(key: str) -> dict:
    """The licence's contents, *unverified*, for display before setup verifies it."""
    try:
        body = key.strip().split(".")[1]
        return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (IndexError, ValueError):
        raise InstallError("check", "This isn't a Mizan licence key.") from None


def _internal(args: list[str], env: dict[str, str], step: str) -> dict:
    """Run one of this program's internal commands; it prints one JSON line."""
    r = subprocess.run([*self_command(), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, **env},
                       creationflags=0x08000000 if IS_WINDOWS else 0)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("{")]
    result = json.loads(lines[-1]) if lines else {}
    if r.returncode != 0 or not result.get("ok", False):
        raise InstallError(step, result.get("error") or (r.stderr or r.stdout).strip()[-800:] or "failed")
    return result


def _ensure_system_user(name: str, home: Path) -> None:
    if subprocess.run(["id", "-u", name], capture_output=True).returncode == 0:
        return
    nologin = "/usr/sbin/nologin" if Path("/usr/sbin/nologin").exists() else "/bin/false"
    subprocess.run(["useradd", "--system", "--home-dir", str(home), "--shell", nologin, name], check=True)


def _wait_healthy(url: str, timeout: float = 90) -> bool:
    import ssl

    ctx = ssl._create_unverified_context()  # our own certificate; just checking it's up
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=5, context=ctx) as r:
                if json.loads(r.read()).get("status") == "ok":
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(1.5)
    return False


def install(
    *,
    licence_key: str,
    admin_password: str,
    emit: Emit,
    admin_username: str | None = None,
    admin_name: str | None = None,
    data_dir: Path | None = None,
    port: int | None = None,
    demo: bool = False,
    cloud_url: str | None = None,
    app_env: str = "production",
    with_service: bool = True,
    licence_public_key: str = "",
) -> dict:
    # ── check ───────────────────────────────────────────────────────────────
    emit("check", "running")
    if len(admin_password) < 8:
        raise InstallError("check", "The admin password must be at least 8 characters.")
    claims = peek_licence(licence_key)
    mode = claims.get("mode")
    if mode not in ("desktop", "lan"):
        raise InstallError("check", "This licence isn't for a single-device or LAN workspace.")
    root = install_root()
    if not (root / "pgsql" / "bin").exists() or not (root / "web" / "index.html").exists():
        raise InstallError("check", f"The installation files are incomplete in {root}.")
    data = (data_dir or default_data_dir()).resolve()
    free = shutil.disk_usage(data.parent if not data.exists() else data).free
    if free < 1_000_000_000:
        raise InstallError("check", f"At least 1 GB of free disk space is needed ({free // 1_000_000} MB free).")
    workspace = claims.get("workspace", {})
    emit("check", "done", workspace=workspace.get("name"), mode=mode, valid_until=claims.get("valid_until"))

    # ── prepare: configuration, folders, system user ─────────────────────────
    emit("prepare", "running")
    existing = None
    try:
        existing = Config.load(data)
    except FileNotFoundError:
        pass
    if existing and existing.mode != mode:
        raise InstallError("prepare", f"This computer already runs a {existing.mode} install of Mizan.")
    run_as = None
    if not IS_WINDOWS and is_admin():
        run_as = "mizan"
        _ensure_system_user(run_as, data)
    if existing:
        cfg = existing
        cfg.install_dir = str(root)
        cfg.cloud_url = cloud_url or cfg.cloud_url
        cfg.app_env = app_env
        cfg.licence_public_key = licence_public_key or cfg.licence_public_key
    else:
        if mode == "desktop":
            host, http_port, tls = "127.0.0.1", port or postgres.free_port(47800), False
        else:
            preferred = port or (443 if is_admin() else 8443)
            host, http_port, tls = "0.0.0.0", preferred if postgres.port_free(preferred, "0.0.0.0") else postgres.free_port(8443), True
        cfg = Config(mode=mode, install_dir=str(root), data_dir=str(data), http_host=host, http_port=http_port, tls=tls,
                     db_port=postgres.free_port(55432), db_password=secrets.token_urlsafe(24), run_as=run_as,
                     app_env=app_env, cloud_url=cloud_url or "https://mizan-co-owner-api.vercel.app/api",
                     licence_public_key=licence_public_key)
    for sub in ("logs", "backups", "uploads", "mizan", "tls"):
        (cfg.data / sub).mkdir(parents=True, exist_ok=True)
    cfg.save()
    if run_as:
        subprocess.run(["chown", "-R", f"{run_as}:{run_as}", str(cfg.data)], check=True)
    emit("prepare", "done", data_dir=str(cfg.data), install_dir=str(cfg.install))

    # ── database ────────────────────────────────────────────────────────────
    emit("database", "running")
    try:
        if IS_WINDOWS:
            postgres.grant_windows_access(cfg)
        if not postgres.is_initialised(cfg):
            postgres.initdb(cfg)
        postgres.start(cfg)
        postgres.ensure_database(cfg)
    except postgres.PostgresError as e:
        raise InstallError("database", str(e)) from None
    emit("database", "done", port=cfg.db_port)

    # ── workspace: schema, migrations, the licensed workspace and its admin ──
    emit("workspace", "running", workspace=workspace.get("name"))
    args = ["setup-workspace", "--licence", licence_key, "--admin-password", admin_password]
    if admin_username:
        args += ["--admin-username", admin_username]
    if admin_name:
        args += ["--admin-name", admin_name]
    if demo:
        args.append("--demo")
    result = _internal(args, {**cfg.app_environment(), "MIZAN_CONFIG": str(cfg.data / "config.json")}, "workspace")
    if run_as:
        subprocess.run(["chown", "-R", f"{run_as}:{run_as}", str(cfg.data)], check=True)
    emit("workspace", "done", admin=result.get("admin"), admin_created=result.get("admin_created"))

    # ── network: HTTPS certificate for the LAN ───────────────────────────────
    network: dict = {}
    if cfg.tls:
        emit("network", "running")
        from mizan_server.tls import ensure_certificates

        network = ensure_certificates(cfg.data / "tls")
        if run_as:
            subprocess.run(["chown", "-R", f"{run_as}:{run_as}", str(cfg.data / "tls")], check=True)
        emit("network", "done", **network)
    else:
        emit("network", "skipped")

    # ── service ─────────────────────────────────────────────────────────────
    kind = "manual"
    if with_service:
        emit("service", "running")
        postgres.stop(cfg)  # the service owns it from now on
        try:
            kind = service.install(cfg)
        except RuntimeError as e:
            raise InstallError("service", str(e)) from None
        emit("service", "done", kind=kind)
    else:
        postgres.stop(cfg)
        emit("service", "skipped")

    # ── start ───────────────────────────────────────────────────────────────
    url = cfg.url
    if kind != "manual":
        emit("start", "running", url=url)
        local = f"{'https' if cfg.tls else 'http'}://127.0.0.1:{cfg.http_port}"
        if not _wait_healthy(local):
            raise InstallError("start", f"Mizan didn't start. See the logs in {cfg.data / 'logs'}.")
        emit("start", "done", url=url)
    else:
        emit("start", "skipped", hint="Start it with: mizan-server run")

    summary = {
        "url": url,
        "mode": cfg.mode,
        "workspace": workspace.get("name"),
        "admin": result.get("admin"),
        "data_dir": str(cfg.data),
        "service": kind,
        "addresses": [f"{'https' if cfg.tls else 'http'}://{a}" + ("" if cfg.http_port in (80, 443) else f":{cfg.http_port}")
                      for a in network.get("addresses", []) if not a.startswith("127.")],
        "ca_certificate": str(cfg.data / "tls" / "mizan-ca.crt") if cfg.tls else None,
    }
    emit("done", "done", **summary)
    return summary


def _remove_shortcuts() -> None:
    """The desktop and menu shortcuts Mizan Setup created for a single-device install."""
    if IS_WINDOWS:
        public = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
        programs = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        paths = [public / "Desktop" / "Mizan.lnk", programs / "Mizan.lnk"]
    else:
        data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        paths = [data / "applications" / "mizan.desktop", Path.home() / "Desktop" / "mizan.desktop"]
    for path in paths:
        path.unlink(missing_ok=True)


def uninstall(*, delete_data: bool, emit: Emit, data_dir: Path | None = None) -> None:
    cfg = Config.load(data_dir)
    emit("remove-service", "running")
    service.uninstall(cfg)
    postgres.stop(cfg)
    emit("remove-service", "done")
    _remove_shortcuts()
    if delete_data:
        emit("data", "running")
        shutil.rmtree(cfg.data, ignore_errors=True)
        emit("data", "done")
    else:
        emit("data", "skipped", kept=str(cfg.data))
