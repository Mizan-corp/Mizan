"""Database backups: <data>/backups/mizan-YYYYmmdd-HHMMSS.dump (PostgreSQL custom
format), the newest 14 kept, optionally copied to another folder (USB, network
share). The time of the last backup is reported to Mizan Cloud on check-in."""
from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from mizan_server import postgres
from mizan_server.layout import Config

KEEP = 14


def backup_dir(cfg: Config) -> Path:
    return cfg.data / "backups"


def list_backups(cfg: Config) -> list[Path]:
    return sorted(backup_dir(cfg).glob("mizan-*.dump"), reverse=True)


def _record(cfg: Config, when: datetime) -> None:
    state = cfg.data / "mizan" / "state.json"
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data["last_backup_at"] = when.isoformat()
    state.parent.mkdir(parents=True, exist_ok=True)
    tmp = state.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, state)


def run_backup(cfg: Config, copy_to: Path | None = None) -> Path:
    """Back up now; also copy it to `copy_to`, else to the configured destination (#90)."""
    postgres.start(cfg)
    now = datetime.now(UTC)
    target = backup_dir(cfg) / f"mizan-{now:%Y%m%d-%H%M%S}.dump"
    postgres.dump(cfg, target)
    for old in list_backups(cfg)[KEEP:]:
        old.unlink(missing_ok=True)
    _record(cfg, now)
    destination = copy_to or (Path(cfg.backup_copy_to) if cfg.backup_copy_to else None)
    if destination:
        try:
            copy_backup(target, destination)
            _record_copy(cfg, None)
        except OSError as e:
            # An unplugged drive or an unreachable share mustn't lose the backup itself.
            _record_copy(cfg, f"{destination}: {e}")
            if copy_to:
                raise
    return target


def copy_backup(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    copied = destination / source.name
    partial = destination / (source.name + ".part")
    shutil.copyfile(source, partial)
    os.replace(partial, copied)
    for old in sorted(destination.glob("mizan-*.dump"), reverse=True)[KEEP:]:
        old.unlink(missing_ok=True)
    return copied


def _record_copy(cfg: Config, error: str | None) -> None:
    state = cfg.data / "mizan" / "state.json"
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data["backup_copy_error"] = error
    if error is None:
        data["last_backup_copy_at"] = datetime.now(UTC).isoformat()
    state.parent.mkdir(parents=True, exist_ok=True)
    tmp = state.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, state)


def restore_backup(cfg: Config, source: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    # Keep what's there now, in case the restore was a mistake.
    run_backup(cfg)
    postgres.restore(cfg, source)
