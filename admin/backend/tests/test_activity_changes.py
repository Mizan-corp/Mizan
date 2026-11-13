"""Changing a workspace's activity (#107): the owner asks, the Mizan team approves (applied) or rejects."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db.base import AsyncSessionLocal
from app.framework.composition import base_modules
from app.platform.auth.models.owner import OwnerAccount
from app.platform.auth.security import hash_password
from app.platform.tenancy import activity_change as changes
from app.platform.tenancy.models import Tenant
from main import app
from tests.test_owners import admin_headers

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def pharmacy_workspace() -> tuple[OwnerAccount, Tenant]:
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        tag = uuid.uuid4().hex[:8]
        owner = OwnerAccount(id=uuid.uuid4(), login=f"own-{tag}", full_name="Owner", password_hash=hash_password("secret123"))
        db.add(owner)
        await db.flush()
        t = Tenant(id=uuid.uuid4(), name=f"Pharmacy {tag}", slug=f"ph-{tag}", sector="pharmacy", business_type="pharmacy",
                   plan="trial", owner_account_id=owner.id, active_modules=base_modules("pharmacy"))
        db.add(t)
        await db.commit()
        return owner, t


async def ask(tenant_id, owner_id, to: str, mode: str = "keep") -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        t = await db.get(Tenant, tenant_id)
        change = await changes.request(db, t, owner_id, to, mode, "we became a restaurant")
        await db.commit()
        return change.id


async def test_approving_converts_the_workspace():
    owner, tenant = await pharmacy_workspace()
    change_id = await ask(tenant.id, owner.id, "restaurant")
    h = await admin_headers()
    async with client() as c:
        # Needs you, and the list.
        attention = (await c.get("/admoon/overview", headers=h)).json()["attention"]
        assert any(a["kind"] == "activity_change" and a["change_id"] == str(change_id) for a in attention)
        assert str(change_id) in {i["id"] for i in (await c.get("/admoon/activity-changes", headers=h)).json()["items"]}

        # The detail carries a fresh preview.
        detail = (await c.get(f"/admoon/activity-changes/{change_id}", headers=h)).json()
        p = detail["preview"]
        assert detail["to"]["id"] == "restaurant" and detail["note"] == "we became a restaurant"
        leaving = {m["id"] for m in p["leaving"]}
        joining = {m["id"] for m in p["joining"]}
        assert {"pharmacy", "batches"} <= leaving
        assert joining and joining <= set(base_modules("restaurant"))
        assert any(m["id"] == "pos" for m in p["variants_changed"])

        r = await c.post(f"/admoon/activity-changes/{change_id}/approve", headers=h, json={"note": "ok"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "applied"
        # Decided once.
        assert (await c.post(f"/admoon/activity-changes/{change_id}/approve", headers=h, json={})).status_code == 409

    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        t = await db.get(Tenant, tenant.id)
        assert t.sector == "restaurant" and t.business_type == "restaurant"
        assert not leaving & set(t.active_modules) and joining <= set(t.active_modules)
        kept = set((await db.execute(text(
            "SELECT module_id FROM module_retention WHERE tenant_id = :t AND mode = 'kept'"), {"t": tenant.id})).scalars())
        assert leaving <= kept  # hidden for 30 days, not deleted
        change = await db.get(changes.ActivityChange, change_id)
        assert change.result["removed"] and set(change.result["added"]) == joining
        note = await db.scalar(text("SELECT title FROM notifications WHERE tenant_id = :t ORDER BY created_at DESC LIMIT 1"), {"t": tenant.id})
        assert note == "تغيّر نشاط المنشأة"


async def test_rejecting_needs_a_reason_and_one_open_request_at_a_time():
    owner, tenant = await pharmacy_workspace()
    change_id = await ask(tenant.id, owner.id, "retail", "delete")
    with pytest.raises(Exception):  # one open request per workspace
        await ask(tenant.id, owner.id, "restaurant")
    h = await admin_headers()
    async with client() as c:
        assert (await c.post(f"/admoon/activity-changes/{change_id}/reject", headers=h, json={})).status_code == 422
        r = await c.post(f"/admoon/activity-changes/{change_id}/reject", headers=h, json={"note": "Talk to us first"})
        assert r.status_code == 200 and r.json()["status"] == "rejected"
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        assert (await db.get(Tenant, tenant.id)).sector == "pharmacy"
        assert await db.scalar(select(changes.ActivityChange.decision_note).where(changes.ActivityChange.id == change_id)) == "Talk to us first"
    # After a decision, a new request is allowed.
    assert await ask(tenant.id, owner.id, "restaurant")
