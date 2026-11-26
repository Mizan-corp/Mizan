"""Undeployed platform-admin adapter. Never substitutes tenant-admin endpoints."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.factory import create_app
from app.platform.auth.routes import auth
from admin_api.routers import activity, activity_changes, billing, marketplace, overview, owners, system, team, workspaces

_service = create_app(
    title="Mizan isolated test platform admin API",
    routers=[auth.router, overview.router, workspaces.router, owners.router, billing.router,
             activity.router, activity_changes.router, marketplace.router, team.router, system.router],
    create_tables=False,
)

async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        prefix = "/admin-api"
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
