"""Serve the harness site API on 127.0.0.1:8791 for the TS client round-trip.

Same real stack as run_http_tests.py (real router/service/auth/tenancy on the local
Postgres subset). Seeds one workspace with a site.manage role and prints a harness JWT
to /tmp/pgtest/roundtrip_token.txt for the node round-trip script.
"""
import os
import sys

sys.path.insert(0, os.environ.get("STUDIO_BACKEND_ROOT", "/tmp/pgtest"))  # dir containing app/ (system/core/backend in the repo)
os.environ["DATABASE_URL"] = "postgresql://postgres@/postgres?host=" + os.environ.get("STUDIO_PGDATA", "/tmp/pgdata2")

import datetime as _dt  # noqa: E402

if not hasattr(_dt, "UTC"):
    _dt.UTC = _dt.timezone.utc

import uuid  # noqa: E402

import pgserver  # noqa: E402
import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402

psycopg2.extras.register_uuid()
pgserver.get_server(os.environ.get("STUDIO_PGDATA", "/tmp/pgdata2"))

from fastapi import FastAPI  # noqa: E402

from app.db.base import Base, engine  # noqa: E402
from app.platform.tenancy.context import install_tenancy_events  # noqa: E402

install_tenancy_events()

import app.platform.tenancy.models  # noqa: E402,F401
import sqlalchemy as _sa  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as _UUID  # noqa: E402

if "owner_accounts" not in Base.metadata.tables:
    _sa.Table("owner_accounts", Base.metadata, _sa.Column("id", _UUID(as_uuid=True), primary_key=True))

import app.activities.general.modules.inventory.models.warehouse as wh  # noqa: E402
import app.platform.permissions.models  # noqa: E402,F401
from app.platform.auth.models.user import User, user_warehouses  # noqa: E402
from app.platform.auth.security import create_access_token  # noqa: E402
from app.platform.site.router import router as site_router  # noqa: E402

app = FastAPI()

# Harness-only fault injection for the studio e2e: lets a test flip PUT /site/settings
# to fail while every other endpoint keeps working, so the partial-save path is real.
_FAIL_SETTINGS = {"on": False}


@app.post("/__test/fail-settings")
async def fail_settings_toggle(on: bool = True):
    _FAIL_SETTINGS["on"] = on
    return {"fail_settings": _FAIL_SETTINGS["on"]}


@app.middleware("http")
async def settings_fault_gate(request, call_next):
    if _FAIL_SETTINGS["on"] and request.method == "PUT" and request.url.path == "/site/settings":
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "injected settings failure"}, status_code=500)
    return await call_next(request)


app.include_router(site_router)


@app.on_event("startup")
async def seed() -> None:
    async with engine.begin() as c:
        await c.run_sync(lambda s: Base.metadata.create_all(
            s, tables=[wh.Warehouse.__table__, User.__table__, user_warehouses]))
    ta, ra, ua = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DELETE FROM tenants WHERE name LIKE 'site-%'")
    cur.execute("INSERT INTO tenants (id, name, sector, scale) VALUES (%s, %s, 'retail', 'small')", (ta, f"site-{ta.hex[:8]}"))
    cur.execute("INSERT INTO sys_roles (id, tenant_id, code, name, grants) VALUES (%s, %s, 'site-admin', 'Site admin', '[\"site.manage\"]')", (ra, ta))
    cur.execute("""INSERT INTO users (id, tenant_id, username, full_name, role, password_hash, is_active, is_manager, active_role_id)
        VALUES (%s, %s, 'admina', 'Admin A', 'admin', 'x', true, false, %s)""", (ua, ta, ra))
    cur.execute("INSERT INTO user_role_assignments (user_id, role_id) VALUES (%s, %s)", (ua, ra))
    conn.close()
    token = create_access_token({"sub": str(ua), "tid": str(ta)})
    with open(os.path.join(os.environ.get("STUDIO_BACKEND_ROOT", "/tmp/pgtest"), "roundtrip_token.txt"), "w") as f:
        f.write(token)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8791, log_level="warning")
