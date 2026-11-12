"""Mizan Admin API: the platform control plane (super-admins only)."""
from admin_api.routers import activity, billing, overview, owners, system, team, workspaces
from app.platform.auth.routes import auth as auth
from app.factory import create_app

app = create_app(
    title="Mizan Admin API",
    routers=[
        auth.router,
        overview.router,
        workspaces.router,
        owners.router,
        billing.router,
        activity.router,
        team.router,
        system.router,
    ],
)
