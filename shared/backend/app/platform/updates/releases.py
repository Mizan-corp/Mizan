"""Published installers for single-device and LAN workspaces (ADR-005).

Set MIZAN_INSTALLERS on the owner API to a JSON object pointing at the files the
Installers workflow builds (installer/README.md), e.g.
  {"windows": {"url": "https://…/MizanSetup-1.0.0-windows.exe", "version": "1.0.0", "size_mb": 140},
   "linux":   {"url": "https://…/MizanSetup-1.0.0-linux", "version": "1.0.0", "size_mb": 141}}
The same Mizan Setup installs single-device and LAN workspaces on both platforms;
the licence decides which. Unset, the list is empty and the owner panel says so.

Updates for installed servers (#89): an entry may also carry the release's payload (the
payload-<version>-<platform>.zip that installer/build.py makes) as "payload_url" and
"payload_sha256". Installs that check in with an older version are offered it, signed with the
licence key under the release prefix (MZR1), so they verify it offline with the key they trust.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("mizan.releases")

PLATFORMS = ("windows", "linux")


def published_installers(mode: str | None = None) -> list[dict]:
    raw = os.environ.get("MIZAN_INSTALLERS", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("MIZAN_INSTALLERS isn't valid JSON")
        return []
    out = []
    for platform in PLATFORMS:
        item = data.get(platform)
        if isinstance(item, dict) and item.get("url"):
            out.append({"platform": platform, "url": item["url"], "version": item.get("version"), "size_mb": item.get("size_mb")})
    return out


def _version_tuple(v: str | None) -> tuple[int, ...]:
    parts = []
    for piece in (v or "").split("-")[0].split("."):
        parts.append(int(piece) if piece.isdigit() else 0)
    return tuple(parts) or (0,)


def is_newer(candidate: str | None, current: str | None) -> bool:
    return bool(candidate) and _version_tuple(candidate) > _version_tuple(current)


def platform_of(os_name: str | None) -> str | None:
    """'Windows 10' → windows, 'Linux 6.8…' → linux (what check-ins report)."""
    name = (os_name or "").lower()
    return "windows" if name.startswith("windows") else "linux" if name.startswith("linux") else None


def update_offer(os_name: str | None, current_version: str | None) -> dict | None:
    """A signed offer of the newest payload for this platform, if it's newer than the install's."""
    from app.platform.licensing import keys

    platform = platform_of(os_name)
    if not platform:
        return None
    raw = os.environ.get("MIZAN_INSTALLERS", "").strip()
    try:
        item = (json.loads(raw) if raw else {}).get(platform) or {}
    except ValueError:
        return None
    version, url, sha = item.get("version"), item.get("payload_url"), item.get("payload_sha256")
    if not (version and url and sha) or not is_newer(version, current_version) or not keys.can_sign():
        return None
    release = {"version": version, "platform": platform, "url": url, "sha256": sha.lower(),
               "notes": item.get("notes") or ""}
    return {"version": version, "release": keys.sign(release, prefix=keys.RELEASE_PREFIX)}


def latest_for(os_name: str | None, current_version: str | None) -> str | None:
    """The newest published version for this install's platform when it's newer (for the panels)."""
    platform = platform_of(os_name)
    for item in published_installers():
        if item["platform"] == platform and is_newer(item.get("version"), current_version):
            return item["version"]
    return None
