"""Updating an installed server to a newer release (#89, ADR-005 phase 2).

`mizan-server update` (run by an administrator on the server):
  1. the release Mizan Cloud offered at the last check-in (`--check` checks in first), verified
     with the licence public key (release prefix MZR1) and newer than this install;
  2. refuses while a till shift is open, unless --force (a LAN server mid-shift);
  3. downloads the release payload and checks its SHA-256;
  4. backs up the database;
  5. unpacks it outside the program folder (<data>/updates/<version>) and starts that version's
     `mizan-server apply-update` on its own, then follows it.

`apply-update` runs from the unpacked copy, so nothing it replaces is in use: it stops the
service, moves the program folder aside (<program>.previous), copies the new one in (keeping
files the payload doesn't have, such as the desktop app), runs the migrations, starts the service
and waits for it to answer. Any failure puts the previous folder back, restores the backup when
the migrations had started, and starts the old version again. The outcome is kept in the
install's state (`last_update`), shown by `mizan-server status` and the app.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import time
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from mizan_server import postgres, service
from mizan_server.layout import EXE, IS_WINDOWS, Config, version

PLATFORM = "windows" if IS_WINDOWS else "linux"


class UpdateError(Exception):
    pass


def _log(cfg: Config, message: str) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {message}"
    print(line, flush=True)
    try:
        (cfg.data / "logs").mkdir(parents=True, exist_ok=True)
        with open(cfg.data / "logs" / "update.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) if p.isdigit() else 0 for p in v.split("-")[0].split(".")) or (0,)


def offered_release() -> dict | None:
    """The verified release offer kept by the last check-in, if newer than this install."""
    from app.onprem import checkin, state
    from app.platform.licensing.keys import LicenceError

    offer = state.read_state().get("update_available") or {}
    if not offer.get("release"):
        return None
    try:
        release = checkin.verified_release(offer["release"])
    except LicenceError as e:
        raise UpdateError(f"The update offer isn't genuine: {e}") from None
    if release["platform"] != PLATFORM:
        raise UpdateError(f"The update offer is for {release['platform']}, not {PLATFORM}.")
    if _version_tuple(release["version"]) <= _version_tuple(version()):
        return None
    return release


def open_shifts(cfg: Config) -> int:
    """Till shifts still open (a LAN server shouldn't be updated mid-shift)."""
    import asyncio

    started = False
    if not postgres.running(cfg):
        postgres.start(cfg)
        started = True
    try:
        async def count() -> int:
            from sqlalchemy import text

            from app.db.base import engine

            async with engine.connect() as conn:
                await conn.execute(text("SELECT set_config('app.bypass', 'on', false)"))
                n = await conn.scalar(text("SELECT count(*) FROM shifts WHERE status = 'open'"))
            await engine.dispose()
            return int(n or 0)

        return asyncio.run(count())
    finally:
        if started:
            postgres.stop(cfg)


def download(cfg: Config, release: dict) -> Path:
    folder = cfg.data / "updates"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"payload-{release['version']}-{release['platform']}.zip"
    if target.exists() and _sha256(target) == release["sha256"]:
        return target
    partial = target.with_suffix(".part")
    _log(cfg, f"Downloading {release['url']}")
    with urllib.request.urlopen(release["url"], timeout=60) as res, open(partial, "wb") as out:
        shutil.copyfileobj(res, out, 1024 * 1024)
    if _sha256(partial) != release["sha256"]:
        partial.unlink(missing_ok=True)
        raise UpdateError("The download doesn't match the release's checksum; nothing was changed.")
    os.replace(partial, target)
    return target


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stage(cfg: Config, archive: Path, release: dict) -> Path:
    """Unpack the payload to <data>/updates/<version> (fresh), keeping executable bits."""
    target = cfg.data / "updates" / release["version"]
    if target.exists():
        shutil.rmtree(target)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            path = Path(z.extract(info, target))
            mode = (info.external_attr >> 16) & 0o777
            if mode and not IS_WINDOWS:
                path.chmod(mode)
    staged_version = (target / "VERSION").read_text(encoding="utf-8").strip() if (target / "VERSION").exists() else ""
    if staged_version != release["version"] or not (target / "server" / f"mizan-server{EXE}").exists():
        raise UpdateError("The release payload is incomplete; nothing was changed.")
    for old in (cfg.data / "updates").iterdir():  # earlier releases' leftovers
        if old.is_dir() and old != target:
            shutil.rmtree(old, ignore_errors=True)
    return target


def backup_now(cfg: Config) -> Path:
    """A database backup before updating (starting PostgreSQL for it if the service is stopped)."""
    from mizan_server.backup import run_backup

    started = False
    if not postgres.running(cfg):
        postgres.start(cfg)
        started = True
    try:
        return run_backup(cfg, None)
    finally:
        if started:
            postgres.stop(cfg)


def launch_apply(cfg: Config, staged: Path, backup: Path) -> None:
    exe = staged / "server" / f"mizan-server{EXE}"
    cmd = [str(exe), "--data-dir", str(cfg.data), "apply-update", "--from", str(staged), "--backup", str(backup)]
    log = open(cfg.data / "logs" / "update.log", "a", encoding="utf-8")  # noqa: SIM115 (the child keeps it)
    if IS_WINDOWS:
        flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    else:
        subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)


def _record(outcome: dict) -> None:
    from app.onprem import state

    changes = {"last_update": outcome}
    if outcome.get("ok"):
        changes["update_available"] = None
    state.update_state(**changes)


def _wait_stopped(cfg: Config, timeout: float = 90) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline and service.control(cfg, "status"):
        time.sleep(1)
    try:
        postgres.stop(cfg)
    except postgres.PostgresError:
        pass


def _migrate(cfg: Config) -> None:
    """The new version's schema and migrations (the install's own idempotent setup)."""
    from app.onprem import state

    key = state.licence_key()
    if not key:
        raise UpdateError("This install has no licence key.")
    exe = cfg.install / "server" / f"mizan-server{EXE}"
    args = [str(exe), "--data-dir", str(cfg.data), "setup-workspace", "--licence", key,
            # Only used when the workspace has no admin, which an installed one always has.
            "--admin-password", secrets.token_urlsafe(18)]
    env = {**os.environ, **cfg.app_environment(), "MIZAN_CONFIG": str(cfg.data / "config.json")}
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                       creationflags=0x08000000 if IS_WINDOWS else 0)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("{")]
    result = json.loads(lines[-1]) if lines else {}
    if r.returncode != 0 or not result.get("ok", False):
        raise UpdateError("Migrations failed: " + (result.get("error") or (r.stderr or r.stdout).strip()[-500:]))


def apply(cfg: Config, staged: Path, backup: Path) -> bool:
    """Replace the program with `staged`; roll back on any failure. True if updated."""
    from mizan_server.engine import _wait_healthy

    old_version = version_of(cfg.install)
    new_version = version_of(staged)
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    previous = cfg.install.with_name(cfg.install.name + ".previous")
    _log(cfg, f"Updating {old_version} → {new_version}")

    # Installs without a service (--no-service, or run by hand) are updated in place; whoever
    # runs them starts the new version.
    managed = service.control(cfg, "status")
    if managed:
        service.control(cfg, "stop")
    _wait_stopped(cfg)
    if previous.exists():
        shutil.rmtree(previous)
    try:
        os.replace(cfg.install, previous)
    except OSError as e:
        if managed:
            service.control(cfg, "start")
        message = f"The program folder is in use ({e}). Close Mizan windows on this computer and try again."
        _log(cfg, message)
        _record({"from": old_version, "to": new_version, "at": started_at, "ok": False, "error": message})
        return False

    migrated = False
    try:
        shutil.copytree(staged, cfg.install)
        for item in previous.iterdir():  # e.g. the desktop app, which the payload doesn't carry
            if not (cfg.install / item.name).exists():
                (shutil.copytree if item.is_dir() else shutil.copy2)(item, cfg.install / item.name)
        postgres.start(cfg)
        migrated = True
        _migrate(cfg)
        postgres.stop(cfg)
        if cfg.run_as:
            subprocess.run(["chown", "-R", f"{cfg.run_as}:{cfg.run_as}", str(cfg.data)], check=False)
        if managed:
            if not service.control(cfg, "start"):
                raise UpdateError("The service didn't start.")
            local = f"{'https' if cfg.tls else 'http'}://127.0.0.1:{cfg.http_port}"
            if not _wait_healthy(local):
                raise UpdateError("The new version didn't answer.")
    except Exception as e:  # anything: put the previous version back
        _log(cfg, f"Update failed ({e}); restoring {old_version}")
        if managed:
            service.control(cfg, "stop")
        _wait_stopped(cfg)
        shutil.rmtree(cfg.install, ignore_errors=True)
        os.replace(previous, cfg.install)
        if migrated:
            postgres.start(cfg)
            postgres.restore(cfg, backup)
            postgres.stop(cfg)
        if managed:
            service.control(cfg, "start")
        _record({"from": old_version, "to": new_version, "at": started_at, "ok": False, "error": str(e)[:300]})
        return False

    shutil.rmtree(previous, ignore_errors=True)
    _log(cfg, f"Updated to {new_version}")
    _record({"from": old_version, "to": new_version, "at": started_at, "ok": True, "error": None})
    return True


def version_of(folder: Path) -> str:
    path = folder / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "unknown"
