"""Mizan Website API: plans, self-serve signup, and the developer portal (ADR-007)."""
from app.factory import create_app
from website_api.routers import branding, developers, public_pages, signup, uploads

app = create_app(
    title="Mizan Website API",
    routers=[signup.router, signup.assets_router, developers.router, public_pages.router, branding.router, uploads.router],
    # No blanket /uploads mount here: uploads.router serves only recorded
    # public site-asset kinds, so business documents (po_invoice) and
    # unrecorded paths stay unreachable for anonymous visitors.
)
