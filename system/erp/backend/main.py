"""Mizan System API: the ERP that tenants use every day.

In the cloud this is the API alone. On a single-device or LAN install
(MIZAN_MODE=desktop|lan) it also serves the app, enforces the licence and checks
in with Mizan Cloud: see app.onprem.server.
"""
from app.core.config import settings
from app.factory import create_app
from system_api.router import router

app = create_app(
    title="Mizan System API",
    routers=[router],
    create_tables=settings.MIZAN_MODE == "cloud",
    serve_files=True,
)

if settings.MIZAN_MODE in ("desktop", "lan"):
    from app.onprem.server import build_server_app

    app = build_server_app(app)
