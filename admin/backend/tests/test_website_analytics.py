"""The website's visit counters in the admin panel (ADR-016): super-admins only, counts only."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from main import app
from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password
from app.platform.site_analytics import service
from app.platform.tenancy.models import Tenant

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


async def admin_headers() -> dict:
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        tag = uuid.uuid4().hex[:8]
        home = Tenant(id=uuid.uuid4(), name=f"Platform test {tag}", slug=f"plat-{tag}")
        db.add(home)
        await db.flush()
        user = User(id=uuid.uuid4(), tenant_id=home.id, username=f"plat-{tag}", full_name="Platform test", role="superadmin",
                    is_superadmin=True, password_hash=hash_password("x"))
        db.add(user)
        await db.commit()
        return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


async def test_super_admins_read_the_totals_and_no_one_else():
    path = f"/test-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            for _ in range(3):
                await service.record(db, kind="pageview", name="page_view", path=path, lang="en")
            await service.record(db, kind="event", name="phone_click", path=path, lang="en")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.get("/admoon/website/analytics")).status_code == 401
            r = await c.get("/admoon/website/analytics", params={"days": 7}, headers=await admin_headers())
            assert r.status_code == 200, r.text
            body = r.json()
            assert {"path": path, "views": 3} in body["pages"]
            assert {"name": "phone_click", "path": path, "count": 1} in body["event_pages"]
            assert body["days"] == 7
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM site_analytics_daily WHERE path = :p"), {"p": path})
            await db.commit()
