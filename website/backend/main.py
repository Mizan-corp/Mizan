"""Mizan Website API: plans, self-serve signup, the developer portal (ADR-007) and the website's
cookieless visit counters (ADR-016)."""
from app.factory import create_app
from website_api.routers import analytics, developers, signup

app = create_app(
    title="Mizan Website API",
    routers=[signup.router, developers.router, analytics.router],
)
