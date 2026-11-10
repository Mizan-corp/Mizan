#!/usr/bin/env python3
"""Upload Mizan's card payment page to Paymob (an Accept iframe).

    PAYMOB_API_KEY=… python owner/paymob/upload.py                 # create; prints the new iframe id
    PAYMOB_API_KEY=… PAYMOB_IFRAME_ID=123 python owner/paymob/upload.py   # update it in place

PAYMOB_API_KEY is the dashboard's "API key" (Settings → API keys; the same for test
and live). Set the printed id as PAYMOB_IFRAME_ID on mizan-owner-api.
Only the Python standard library is needed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = os.environ.get("PAYMOB_BASE_URL", "https://accept.paymob.com").rstrip("/")


def _call(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Paymob {method} {path}: HTTP {e.code} {e.read().decode(errors='replace')[:400]}") from None


def main() -> int:
    api_key = os.environ.get("PAYMOB_API_KEY", "").strip()
    if not api_key:
        print(__doc__)
        return 2
    token = _call("POST", "/api/auth/tokens", {"api_key": api_key})["token"]
    content = {
        "name": "Mizan card",
        "description": "Mizan subscriptions: card payment page (owner/paymob/)",
        "content_html": (HERE / "card.html").read_text(encoding="utf-8"),
        "content_css": (HERE / "card.css").read_text(encoding="utf-8"),
        "content_js": (HERE / "card.js").read_text(encoding="utf-8"),
    }
    iframe_id = os.environ.get("PAYMOB_IFRAME_ID", "").strip()
    if iframe_id:
        r = _call("PUT", f"/api/acceptance/iframes/{iframe_id}", content, token)
        print(f"Updated iframe {r.get('id', iframe_id)}")
    else:
        r = _call("POST", "/api/acceptance/iframes", content, token)
        print(f"Created iframe {r.get('id')}: set PAYMOB_IFRAME_ID={r.get('id')} on mizan-owner-api")
    return 0


if __name__ == "__main__":
    sys.exit(main())
