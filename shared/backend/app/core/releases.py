"""Published installers for single-device and LAN workspaces (ADR-005).

Set MIZAN_INSTALLERS on the owner API to a JSON object, e.g.
  {"windows": {"url": "https://…/MizanSetup-1.2.0.exe", "version": "1.2.0", "size_mb": 180},
   "linux":   {"url": "https://…/mizan-setup-1.2.0.AppImage", "version": "1.2.0", "size_mb": 170}}
Until installers are built (phase 2) the list is empty and the owner panel says so.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("mizan.releases")

PLATFORMS = ("windows", "linux")


def published_installers(mode: str) -> list[dict]:
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
            # A single-device install is Windows-only; LAN servers can also run on Linux.
            if mode == "desktop" and platform != "windows":
                continue
            out.append({"platform": platform, "url": item["url"], "version": item.get("version"), "size_mb": item.get("size_mb")})
    return out
