"""Mizan Website API: plans, self-serve signup, and the developer portal (ADR-007)."""
from app.factory import create_app
from website_api.routers import branding, developers, public_pages, signup

app = create_app(
    title="Mizan Website API",
    routers=[signup.router, signup.assets_router, developers.router, public_pages.router, branding.router],
)
