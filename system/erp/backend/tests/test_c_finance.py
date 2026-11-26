"""Finance, phase C (PRODUCTION_READINESS.md, `finance`).

FIN-9  `strict_safe_balance` is honoured: approving an expense above its safe's balance is refused
       unless the workspace turned the setting off; recurring expenses recur (a nightly job makes the
       next draft when it is due, once).
FIN-14 the rules the new screens rely on: only a draft is edited in full or decided; after a
       decision the notes and the recurrence still change; the expense list is paged.
"""
import json
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.db.base import AsyncSessionLocal
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from tests.test_ready_finance import _client, _one, _sql, _ws

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

D = Decimal
ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _expense(c, h, **body) -> dict:
    r = await c.post("/expenses", headers=h, json={"description": "إيجار", **body})
    assert r.status_code == 201, r.text
    return r.json()


# ── FIN-9: strict_safe_balance ───────────────────────────────────────────────────────────────

async def test_an_expense_above_the_safes_balance_is_refused_while_the_setting_is_on():
    """Old code: the setting was never read and the approval took the safe below zero."""
    env = await _ws()
    h = env["h"]["admin"]
    async with _client() as c:
        big = await _expense(c, h, amount="1500", safe_id=str(env["safe_id"]))  # the safe holds 1000
        r = await c.post(f"/expenses/{big['id']}/approve", headers=h, json={"approved": True})
        assert r.status_code == 400 and "رصيد الخزنة غير كافٍ" in r.json()["detail"]
        assert await _one(env, "SELECT balance FROM safes WHERE id = :s", s=env["safe_id"]) == D("1000.00")
        assert await _one(env, "SELECT status FROM expenses WHERE id = :i", i=uuid.UUID(big["id"])) == "draft"

        small = await _expense(c, h, amount="400", safe_id=str(env["safe_id"]))
        assert (await c.post(f"/expenses/{small['id']}/approve", headers=h, json={"approved": True})).status_code == 200
        assert await _one(env, "SELECT balance FROM safes WHERE id = :s", s=env["safe_id"]) == D("600.00")

        # Switched off in the module centre: the overdraft is the workspace's choice.
        await _sql(env, "INSERT INTO store_settings (key, value) VALUES ('mod_settings_finance', :v) "
                        "ON CONFLICT (tenant_id, key) DO UPDATE SET value = EXCLUDED.value",
                   v=json.dumps({"strict_safe_balance": False}))
        r = await c.post(f"/expenses/{big['id']}/approve", headers=h, json={"approved": True})
        assert r.status_code == 200, r.text
        assert await _one(env, "SELECT balance FROM safes WHERE id = :s", s=env["safe_id"]) == D("-900.00")


async def test_a_stopped_safe_pays_no_expense():
    env = await _ws()
    h = env["h"]["admin"]
    async with _client() as c:
        empty = (await c.post("/safes", headers=h, json={"name": "خزنة فارغة"})).json()
        exp = await _expense(c, h, amount="10", safe_id=empty["id"])
        assert (await c.delete(f"/safes/{empty['id']}", headers=h)).status_code in (200, 204)
        r = await c.post(f"/expenses/{exp['id']}/approve", headers=h, json={"approved": True})
        assert r.status_code == 400 and "موقوفة" in r.json()["detail"]


# ── FIN-9: recurring expenses ────────────────────────────────────────────────────────────────

async def test_recurring_expenses_make_their_next_draft_once_when_due():
    """Old code: `is_recurring` was stored and nothing ever recurred (no job)."""
    from app.activities.general.modules.finance.services import recurring
    from app.platform.automation_worker.runner import JOB_REGISTRY

    env = await _ws()
    t = env["tenant_id"]
    today = date(2026, 5, 20)
    monthly = uuid.uuid4()
    for eid, day, interval, status, end in (
        (monthly, date(2026, 2, 28), "monthly", "approved", None),  # due 3/28, 4/28 (5/28 not yet)
        (uuid.uuid4(), date(2026, 5, 15), "weekly", "draft", date(2026, 5, 21)),  # due 5/22: after its end
        (uuid.uuid4(), date(2026, 5, 10), "weekly", "rejected", None),  # due 5/17
    ):
        await _sql(env, """
            INSERT INTO expenses (id, tenant_id, amount, description, date, status, is_recurring, recurring_interval,
                                  recurring_end_date, safe_id, category_id)
            VALUES (:id, :t, 250, 'إيجار المخزن', :d, :st, true, :i, :end, :s, NULL)
        """, id=eid, t=t, d=day, st=status, i=interval, end=end, s=env["safe_id"])
    await _sql(env, "INSERT INTO expenses (id, tenant_id, amount, description, date, status) "
                    "VALUES (gen_random_uuid(), :t, 99, 'مرة واحدة', :d, 'approved')", t=t, d=date(2025, 1, 1))

    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        assert await recurring.create_due(s, today) == 3
        await s.commit()
        assert await recurring.create_due(s, today) == 0  # each occurrence is used once
        await s.commit()

    rows = await _sql(env, "SELECT date, status, amount, recurred_from, safe_id, is_recurring, description FROM expenses "
                           "WHERE recurred_from IS NOT NULL ORDER BY date")
    assert [(r.date, r.status) for r in rows] == [(date(2026, 3, 28), "draft"), (date(2026, 4, 28), "draft"),
                                                  (date(2026, 5, 17), "draft")]
    assert all(r.amount == D("250.00") and r.safe_id == env["safe_id"] and r.is_recurring for r in rows)
    assert rows[0].recurred_from == monthly and rows[1].recurred_from not in (None, monthly)
    # No money moved: they wait for approval.
    assert await _one(env, "SELECT balance FROM safes WHERE id = :s", s=env["safe_id"]) == D("1000.00")

    assert "recurring_expenses" in JOB_REGISTRY
    cron = (ROOT / "deploy/server/mizan-cron.sh").read_text()
    nightly = next(line for line in cron.splitlines() if line.strip().startswith("nightly)"))
    assert "recurring_expenses" in nightly


async def test_the_job_runs_for_every_workspace(monkeypatch):
    from app.platform.automation_worker.runner import run_job
    from app.platform.tenancy import clock

    env = await _ws()
    await _sql(env, "INSERT INTO expenses (id, tenant_id, amount, description, date, status, is_recurring, recurring_interval) "
                    "VALUES (gen_random_uuid(), :t, 5, 'اشتراك', :d, 'approved', true, 'weekly')",
               t=env["tenant_id"], d=clock.today() - timedelta(days=7))
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        out = await run_job("recurring_expenses", s)
    assert out["status"] == "success", out
    assert await _one(env, "SELECT count(*) FROM expenses WHERE recurred_from IS NOT NULL") == 1


# ── FIN-14: the rules behind the screens ─────────────────────────────────────────────────────

async def test_a_decided_expense_changes_only_its_notes_and_recurrence():
    env = await _ws()
    h = env["h"]["admin"]
    async with _client() as c:
        exp = await _expense(c, h, amount="20", safe_id=str(env["safe_id"]), is_recurring=True)
        assert exp["recurring_interval"] == "monthly"  # recurring without an interval: monthly
        r = await c.put(f"/expenses/{exp['id']}", headers=h, json={"amount": "25", "description": "إيجار مايو"})
        assert r.status_code == 200 and r.json()["amount"] == 25.0
        r = await c.post(f"/expenses/{exp['id']}/approve", headers=h, json={"approved": True})
        assert r.status_code == 200
        assert (await c.put(f"/expenses/{exp['id']}", headers=h, json={"amount": "30"})).status_code == 409
        r = await c.put(f"/expenses/{exp['id']}", headers=h, json={"is_recurring": False, "notes": "توقف"})
        assert r.status_code == 200
        assert (r.json()["is_recurring"], r.json()["recurring_interval"], r.json()["notes"]) == (False, None, "توقف")
        r = await c.put(f"/expenses/{exp['id']}", headers=h,
                        json={"is_recurring": True, "recurring_end_date": "2000-01-01"})
        assert r.status_code == 400

        # Rejected: closed, not approved later.
        draft = await _expense(c, h, amount="5")
        r = await c.post(f"/expenses/{draft['id']}/approve", headers=h, json={"approved": False, "notes": "مكرر"})
        assert r.status_code == 200 and r.json()["status"] == "rejected"
        r = await c.post(f"/expenses/{draft['id']}/approve", headers=h,
                         json={"approved": True, "safe_id": str(env["safe_id"])})
        assert r.status_code == 409

        page = (await c.get("/expenses", headers=h, params={"page": 1, "page_size": 1})).json()
        assert page["total"] == 2 and len(page["data"]) == 1
        assert (await c.get("/expenses", headers=h, params={"page_size": 500})).status_code == 422
