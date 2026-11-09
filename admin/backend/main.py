"""Mizan Admin API: the Admoon platform control plane (super-admins only)."""
from admin_api.routers import admoon
from app.api.routers import auth, billing
from app.factory import create_app

app = create_app(
    title="Mizan Admin API",
    routers=[admoon.router, auth.router, billing.router],
)
