"""Deploy the uptime Worker (deploy/uptime/worker.js) to Cloudflare. Standard library only.

    CF_API_TOKEN=... BREVO_API_KEY=... RUN_KEY=... python deploy/uptime/deploy.py

CF_API_TOKEN needs Workers Scripts, Workers KV and Workers Routes (edit) on the account and the
allmizan.live zone. Optional: ALERT_TO (default ammar0xf@gmail.com: not on the server, so alerts
arrive when the server is down).
"""
from __future__ import annotations

import json
import os
import uuid
import urllib.request
from pathlib import Path

ACCOUNT = "311360b43a55b6a77a93173a15336c62"
ZONE = "7f3774977686a1eb2335eaa4a72a74f4"
SCRIPT = "mizan-uptime"
HOST = "status.allmizan.live"
API = "https://api.cloudflare.com/client/v4"
TOKEN = os.environ["CF_API_TOKEN"]


def call(method: str, path: str, body: bytes | dict | list | None = None, content_type: str = "application/json") -> dict:
    data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": content_type})
    try:
        out = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        out = json.load(e)
    if not out.get("success"):
        raise SystemExit(f"{method} {path}: {out.get('errors')}")
    return out["result"]


def kv_namespace() -> str:
    title = "mizan-uptime"
    for ns in call("GET", f"/accounts/{ACCOUNT}/storage/kv/namespaces?per_page=100"):
        if ns["title"] == title:
            return ns["id"]
    return call("POST", f"/accounts/{ACCOUNT}/storage/kv/namespaces", {"title": title})["id"]


def upload(ns: str) -> None:
    metadata = {
        "main_module": "worker.js",
        "compatibility_date": "2026-11-01",
        "bindings": [
            {"type": "kv_namespace", "name": "STATE", "namespace_id": ns},
            {"type": "secret_text", "name": "BREVO_API_KEY", "text": os.environ["BREVO_API_KEY"]},
            {"type": "secret_text", "name": "RUN_KEY", "text": os.environ["RUN_KEY"]},
            {"type": "plain_text", "name": "ALERT_TO", "text": os.environ.get("ALERT_TO", "ammar0xf@gmail.com")},
        ],
    }
    code = (Path(__file__).parent / "worker.js").read_bytes()
    boundary = uuid.uuid4().hex
    parts = [
        (b'Content-Disposition: form-data; name="metadata"; filename="metadata.json"\r\nContent-Type: application/json',
         json.dumps(metadata).encode()),
        (b'Content-Disposition: form-data; name="worker.js"; filename="worker.js"\r\nContent-Type: application/javascript+module',
         code),
    ]
    body = b"".join(b"--" + boundary.encode() + b"\r\n" + h + b"\r\n\r\n" + c + b"\r\n" for h, c in parts) + b"--" + boundary.encode() + b"--\r\n"
    call("PUT", f"/accounts/{ACCOUNT}/workers/scripts/{SCRIPT}", body, f"multipart/form-data; boundary={boundary}")


def schedule() -> None:
    call("PUT", f"/accounts/{ACCOUNT}/workers/scripts/{SCRIPT}/schedules", [{"cron": "*/5 * * * *"}])


def route() -> None:
    pattern = f"{HOST}/*"
    for r in call("GET", f"/zones/{ZONE}/workers/routes"):
        if r["pattern"] == pattern:
            if r.get("script") != SCRIPT:
                call("PUT", f"/zones/{ZONE}/workers/routes/{r['id']}", {"pattern": pattern, "script": SCRIPT})
            return
    call("POST", f"/zones/{ZONE}/workers/routes", {"pattern": pattern, "script": SCRIPT})


if __name__ == "__main__":
    ns = kv_namespace()
    upload(ns)
    schedule()
    route()
    print(f"Deployed {SCRIPT}: every 5 minutes, status at https://{HOST}")
