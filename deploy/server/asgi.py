"""The four Mizan APIs in one process, for the self-hosted server (deploy/server/README.md).

Each API stays its own FastAPI app (system/, website/, owner/, admin/ backend/main.py); this
module only picks the app from the request's host, by its first label:

    api.<domain>        -> system API         owner-api.<domain> -> owner API
    web-api.<domain>    -> website API        admin-api.<domain> -> admin API

and drops the `/api` prefix the apps call (as Vercel's rewrites did). One process instead of
four saves the memory of three Python interpreters and three copies of the shared kernel.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

ROOT = Path(os.environ.get("MIZAN_BACKENDS", "/srv/mizan"))
PRODUCTS = {"api": "system", "owner-api": "owner", "web-api": "website", "admin-api": "admin"}


def _load(product: str):
    folder = ROOT / ("system/erp" if product == "system" else product) / "backend"
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location(f"mizan_{product}_main", folder / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


APPS = {product: _load(product) for product in dict.fromkeys(PRODUCTS.values())}
BY_LABEL = {label: APPS[product] for label, product in PRODUCTS.items()}


async def _respond(send, status: int, body: dict) -> None:
    data = json.dumps(body).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]})
    await send({"type": "http.response.body", "body": data})


async def _lifespan(receive, send) -> None:
    async with AsyncExitStack() as stack:
        await receive()  # lifespan.startup
        try:
            for app in APPS.values():
                await stack.enter_async_context(app.router.lifespan_context(app))
        except Exception as exc:  # noqa: BLE001 - reported to the server, which exits
            await send({"type": "lifespan.startup.failed", "message": str(exc)})
            return
        await send({"type": "lifespan.startup.complete"})
        await receive()  # lifespan.shutdown
    await send({"type": "lifespan.shutdown.complete"})


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        await _lifespan(receive, send)
        return
    if scope["type"] == "http" and scope["path"] == "/healthz":
        await _respond(send, 200, {"status": "ok"})
        return
    host = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"host"), "")
    target = BY_LABEL.get(host.split(":")[0].split(".")[0].lower())
    if target is None:
        if scope["type"] == "http":
            await _respond(send, 404, {"detail": "Unknown API host"})
        return
    path = scope["path"]
    if path == "/api" or path.startswith("/api/"):
        raw = scope.get("raw_path") or path.encode()
        scope = {**scope, "path": path[4:] or "/", "raw_path": raw[4:] or b"/"}
    await target(scope, receive, send)
