"""Mizan owner API: the owner panel, where an owner manages their workspaces,
subscriptions and payments (Paymob)."""
from app.factory import create_app
from owner_api.routers import account, billing, workspaces

app = create_app(
    title="Mizan Owner API",
    routers=[account.router, workspaces.router, billing.router],
)
