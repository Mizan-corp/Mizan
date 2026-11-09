"""The install's identity and licence key, kept in MIZAN_DATA_DIR."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from app.core.config import settings


def data_dir() -> Path:
    path = Path(settings.MIZAN_DATA_DIR).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(name: str, text: str) -> None:
    path = data_dir() / name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:  # Windows
        pass


def installation_id() -> uuid.UUID:
    path = data_dir() / "installation_id"
    if path.exists():
        try:
            return uuid.UUID(path.read_text().strip())
        except ValueError:
            pass
    new = uuid.uuid4()
    _write("installation_id", str(new))
    return new


def licence_key() -> str | None:
    path = data_dir() / "licence.key"
    if path.exists():
        return path.read_text(encoding="utf-8").strip() or None
    return settings.MIZAN_LICENCE.strip() or None


def save_licence_key(key: str) -> None:
    _write("licence.key", key.strip())


def read_state() -> dict:
    path = data_dir() / "state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update_state(**changes) -> dict:
    state = {**read_state(), **changes}
    _write("state.json", json.dumps(state, ensure_ascii=False, indent=2))
    return state
