"""Check in with Mizan Cloud when online: report the install, pick up a renewed key."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import socket
import urllib.error
import urllib.request
from datetime import UTC, datetime

from app.platform.licensing import keys as licensing
from app.core.config import settings
from app.onprem import licence, state

logger = logging.getLogger("mizan.onprem.checkin")

APP_VERSION = os.environ.get("MIZAN_VERSION", "0.0.0-dev")
INTERVAL_SECONDS = 6 * 3600


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read() or b"{}")


async def check_in_once() -> dict:
    key = state.licence_key()
    if not key:
        return {"ok": False, "reason": "no licence"}
    body = {
        "licence_key": key,
        "installation_id": str(state.installation_id()),
        "hostname": socket.gethostname()[:128],
        "os": f"{platform.system()} {platform.release()}"[:64],
        "app_version": APP_VERSION,
        "last_backup_at": state.read_state().get("last_backup_at"),
    }
    url = f"{settings.MIZAN_CLOUD_URL.rstrip('/')}/installations/check-in"
    now = datetime.now(UTC).isoformat()
    try:
        answer = await asyncio.to_thread(_post, url, body)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        # Offline is normal: the install keeps working on its current key.
        state.update_state(last_check_in_error=str(e)[:200], last_check_in_attempt_at=now)
        return {"ok": False, "reason": "offline"}

    _remember_update(answer.get("update"))
    if answer.get("status") == "revoked":
        state.update_state(revoked=True, last_check_in_at=now, last_check_in_error=None)
    elif answer.get("licence_key"):
        try:
            licence.accept_key(answer["licence_key"])
        except licensing.LicenceError as e:
            logger.warning("Check-in returned an unusable key: %s", e)
        state.update_state(last_check_in_at=now, last_check_in_error=None)
    return {"ok": True, "status": answer.get("status")}


def verified_release(signed: str) -> dict:
    """A release offer's contents, after checking Mizan signed it (LicenceError otherwise)."""
    release = licensing.verify(signed, prefix=licensing.RELEASE_PREFIX)
    if not {"version", "platform", "url", "sha256"} <= release.keys():
        raise licensing.LicenceError("Incomplete release offer")
    return release


def _remember_update(offer: dict | None) -> None:
    """Keep a genuine, newer release offer for `mizan-server update` (#89); forget it otherwise."""
    from app.platform.updates.releases import is_newer

    release = None
    if offer and offer.get("release"):
        try:
            release = verified_release(offer["release"])
        except licensing.LicenceError as e:
            logger.warning("Ignored an update offer: %s", e)
    if release and is_newer(release["version"], APP_VERSION):
        state.update_state(update_available={"version": release["version"], "release": offer["release"],
                                             "notes": release.get("notes") or ""})
    else:
        state.update_state(update_available=None)


async def run_forever() -> None:
    while True:
        try:
            await check_in_once()
        except Exception:  # never let the loop die
            logger.exception("Check-in failed")
        await asyncio.sleep(INTERVAL_SECONDS)
