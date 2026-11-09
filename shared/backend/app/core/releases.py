"""Published installers for single-device and LAN workspaces (ADR-005).

Set MIZAN_INSTALLERS on the owner API to a JSON object pointing at the files the
Installers workflow builds (installer/README.md), e.g.
  {"windows": {"url": "https://…/MizanSetup-1.0.0-windows.exe", "version": "1.0.0", "size_mb": 140},
   "linux":   {"url": "https://…/MizanSetup-1.0.0-linux", "version": "1.0.0", "size_mb": 141}}
The same Mizan Setup installs single-device and LAN workspaces on both platforms;
the licence decides which. Unset, the list is empty and the owner panel says so.
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
