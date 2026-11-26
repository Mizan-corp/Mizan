"""Mizan Website API: plans, self-serve signup, the developer portal (ADR-007) and the website's
cookieless visit counters (ADR-016)."""
from app.factory import create_app
from website_api.routers import (analytics, branding, developers, public_forms, public_pages, signup,
                                 uploads)

app = create_app(
    title="Mizan Website API",
    routers=[signup.router, signup.assets_router, developers.router, public_pages.router,
             public_forms.router, branding.router, uploads.router, analytics.router],
    # No blanket /uploads mount here: uploads.router serves only recorded
    # public site-asset kinds, so business documents (po_invoice) and
    # unrecorded paths stay unreachable for anonymous visitors.
)
