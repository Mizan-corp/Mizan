"""Undeployed website adapter, existing signup/developer contracts, no bootstrap."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.factory import create_app
from website_api.routers import public_pages, signup, developers

_service = create_app(title="Mizan isolated test website API", routers=[signup.router, developers.router, public_pages.router], create_tables=False)

async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        prefix = "/website-api"
        path = scope.get("path", "")
        if scope["type"] == "http" and (path == "/site" or path.startswith("/site/")):
            # Anonymous visitor runtime: served at the root /site/* path.
            await _service(scope, receive, send)
            return
        if path != prefix and not path.startswith(prefix + "/"):
            if scope["type"] == "http":
                await send({"type": "http.response.start", "status": 404, "headers": []})
                await send({"type": "http.response.body", "body": b"Not found"})
            else:
                await send({"type": "websocket.close", "code": 1008})
            return
        scope = dict(scope)
        scope["path"] = path[len(prefix):] or "/"
        scope["root_path"] = prefix
    await _service(scope, receive, send)
