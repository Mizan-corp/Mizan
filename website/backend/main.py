"""Mizan Website API: plans and self-serve signup for onboarding."""
from app.factory import create_app
from website_api.routers import signup

app = create_app(
    title="Mizan Website API",
    routers=[signup.router],
)
