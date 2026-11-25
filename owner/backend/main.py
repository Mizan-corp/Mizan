"""Mizan owner API: the owner panel, where an owner manages their workspaces,
subscriptions and payments (Paymob)."""
from app.factory import create_app
from owner_api.routers import account, activity, billing, branding, installations, workspaces

app = create_app(
    title="Mizan Owner API",
    routers=[account.router, activity.catalogue, workspaces.router, activity.router, billing.router, installations.router, branding.router],
)
