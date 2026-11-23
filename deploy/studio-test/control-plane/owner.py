"""Undeployed owner-service adapter. Keeps the existing owner router/auth boundary."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.factory import create_app
from owner_api.routers import account, activity, billing, installations, workspaces

_service = create_app(
    title="Mizan isolated test owner API",
    routers=[account.router, activity.catalogue, workspaces.router, activity.router,
             billing.router, installations.router],
    create_tables=False,
)

async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        prefix = "/owner-api"
        path = scope.get("path", "")
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
