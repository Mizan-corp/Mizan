"""Mizan System API: the ERP that tenants use every day."""
from app.factory import create_app
from system_api.router import router

app = create_app(
    title="Mizan System API",
    routers=[router],
    create_tables=True,
    serve_files=True,
)
