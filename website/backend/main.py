"""Mizan Website API: plans, self-serve signup, and the developer portal (ADR-007)."""
from app.factory import create_app
from website_api.routers import developers, public_pages, signup

app = create_app(
    title="Mizan Website API",
    routers=[signup.router, developers.router, public_pages.router],
)
