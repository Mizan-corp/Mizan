"""Is this install licensed? Expired or revoked → read-only, never locked out."""
from __future__ import annotations

from datetime import UTC, datetime

from app.core import licensing
from app.onprem import state


def current() -> dict:
    key = state.licence_key()
    if not key:
        return {"status": "missing", "payload": None}
    try:
        payload = licensing.verify(key)
    except licensing.LicenceError as e:
        return {"status": "invalid", "payload": None, "error": str(e)}
    if state.read_state().get("revoked"):
        status = "revoked"
    else:
        status = "active" if licensing.is_current(payload) else "expired"
    until = datetime.fromisoformat(payload["valid_until"])
    days_left = (until - datetime.now(UTC)).total_seconds() / 86400
    return {"status": status, "payload": payload, "valid_until": payload["valid_until"], "days_left": int(days_left // 1)}


def is_writable() -> bool:
    return current()["status"] == "active"


def accept_key(new_key: str) -> dict:
    """Install a new key (typed in, or from a check-in). It must be genuine and for
    this workspace; a key for another workspace is refused."""
    payload = licensing.verify(new_key)
    existing = current().get("payload")
    if existing and existing["workspace"]["id"] != payload["workspace"]["id"]:
        raise licensing.LicenceError("This key is for another workspace")
    state.save_licence_key(new_key)
    state.update_state(revoked=False)
    return payload
