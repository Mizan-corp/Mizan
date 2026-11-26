"""Clinical files served only through short-lived signed links (#43, #44).

A clinician who reaches the patient's record asks for a link (an authenticated, logged route);
the link names the file, the user and the workspace and expires after LINK_SECONDS. The link's
route (routes/media.py, outside the session guards so an <img> can load it) checks the signature
and expiry, then checks again that this user still reaches the patient's record, and logs the read.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.framework import signed

PURPOSE = "clinic-media"
LINK_SECONDS = 300


def link(kind: str, record_id: str, user) -> dict:
    token = signed.sign(PURPOSE, {"k": kind, "id": record_id, "u": str(user.id), "t": str(user.tenant_id)}, LINK_SECONDS)
    return {"url": f"/clinic/media/{token}", "expires_at": datetime.now(UTC) + timedelta(seconds=LINK_SECONDS)}
