"""Phase B of production readiness, platform and money modules.

- PLAT-7: ids and dates are typed; bad input is a 422 (or an Arabic 4xx), never a 500; a user's
  branches can only be set to this workspace's branches, for this workspace's users.
- PLAT-8: the workspace's clock (Africa/Cairo) decides the current month for closed periods and the
  date of a new expense, not the server's.
- FIN-15: a rejected expense is closed (not approved later, not edited); a category a drawer
  movement carries is stopped, not deleted (which cleared the movement's category).
- CON-7: the default credit limit setting reaches new customers; customer search has an index.
- ACC-3: accounting reports are limited to the branches of a user who doesn't see every branch;
  a duplicate account number is a 409; a group is stopped only after its accounts; the party picker
  searches on the server.
"""
import json
import os
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import text

from app.activities.general.modules.pos import service as pos_service
from app.activities.general.modules.pos.models import DrawerTxType
from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User, user_warehouses
from app.platform.auth.security import hash_password
from app.platform.tenancy import clock
from app.platform.tenancy.context import current_tenant_id
from tests.conftest import give_roles
from tests.test_reporting import _auth, _client, _scenario, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _user(env: dict, perms: list[str], branches: list) -> uuid.UUID:
    t = env["tenant_id"]
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        u = User(id=uuid.uuid4(), tenant_id=t, username=f"u_{uuid.uuid4().hex[:10]}", full_name="مستخدم", role="cashier",
                 password_hash=hash_password("Pass12345!"), permissions=perms, is_active=True)
        s.add(u)
        await s.flush()
        for wh in branches:
            await s.execute(user_warehouses.insert().values(user_id=u.id, warehouse_id=wh))
        await give_roles(s)
        await s.commit()
    current_tenant_id.set(t)
    return u.id


# ── PLAT-7 ─────────────────────────────────────────────────────────────────────────────────────

async def test_a_users_branches_stay_in_the_workspace_and_bad_ids_are_422s():
    """Fails on the old code: another workspace's user lost their branches, another workspace's
    branch was assigned, and a malformed id was a 500."""
    env, other = await _scenario(), await _scenario()
    admin = _auth(env["cashier_id"], env["tenant_id"])  # the ledger fixture's admin
    clerk = env["users"]["clerk"]
    async with _client() as c:
        r = await c.put(f"/users/{other['users']['clerk']}/warehouses", json={"warehouse_ids": []}, headers=admin)
        assert r.status_code == 404
        assert (await c.get(f"/users/{other['users']['clerk']}/warehouses", headers=admin)).status_code == 404
        r = await c.put(f"/users/{clerk}/warehouses", json={"warehouse_ids": [str(other["warehouse_id"])]}, headers=admin)
        assert r.status_code == 404
        assert (await c.put(f"/users/{clerk}/warehouses", json={"warehouse_ids": ["abc"]}, headers=admin)).status_code == 422
        r = await c.put(f"/users/{clerk}/warehouses", json={"warehouse_ids": [str(env["warehouse2_id"])] * 2}, headers=admin)
        assert r.status_code == 200
        assert (await c.get(f"/users/{clerk}/warehouses", headers=admin)).json() == [str(env["warehouse2_id"])]
        for value, code in (("abc", 422), (str(other["warehouse_id"]), 404), ("", 200), (str(env["warehouse_id"]), 200)):
            r = await c.put(f"/users/{clerk}", json={"default_warehouse_id": value}, headers=admin)
            assert r.status_code == code, (value, r.text[:200])
        mgr = _auth(env["users"]["manager"], env["tenant_id"])
        for params in ({"doc_type": "bogus"}, {"from_date": "yesterday"}, {"limit": 0}):
            assert (await c.get("/archive", params=params, headers=mgr)).status_code == 422, params
        assert (await c.get("/archive", params={"from_date": "2026-02-01", "to_date": "2026-01-01"}, headers=mgr)).status_code == 400
        assert (await c.get("/archive", params={"from_date": "2026-01-01"}, headers=mgr)).status_code == 200
        # The archive holds customers' names and amounts: `archive` reads it, not any signed-in user.
        assert (await c.get("/archive", headers=_auth(env["users"]["cashier"], env["tenant_id"]))).status_code == 403
        assert (await c.get("/modules/retention/abc/export", headers=admin)).status_code == 422
        assert (await c.get("/notifications/tokens", params={"user_id": "abc"}, headers=admin)).status_code == 422
    other_rows = await _sql(other, "SELECT warehouse_id FROM user_warehouses WHERE user_id = :u", u=other["users"]["clerk"])
    assert [r[0] for r in other_rows] == [other["warehouse_id"]]


# ── PLAT-8 ─────────────────────────────────────────────────────────────────────────────────────

def test_the_workspace_clock_is_cairo_time():
    assert clock.local_date(datetime(2026, 1, 31, 22, 30)) == date(2026, 2, 1)  # naive = UTC
    start, end = clock.day_bounds(date(2026, 3, 1), date(2026, 3, 1))
    assert start.isoformat() == "2026-03-01T00:00:00+02:00" and (end - start).days == 1
    assert clock.day_bounds(None, None) == (None, None)


async def test_the_current_month_and_a_new_expenses_date_are_the_workspaces(monkeypatch):
    """Fails on the old code: `require_open_period` used the server's month and a new expense the
    database's date. At 00:30 on 1 May in Cairo (still 30 April in UTC) May is the month."""
    env = await _scenario()
    t, mgr = env["tenant_id"], _auth(env["users"]["manager"], env["tenant_id"])
    monkeypatch.setattr(clock, "now", lambda: datetime(2030, 5, 1, 0, 30, tzinfo=clock.TZ))
    await _sql(env, "INSERT INTO accounting_periods (id, tenant_id, month, status) VALUES (:id, :t, '2030-04', 'closed')",
               id=uuid.uuid4(), t=t)
    async with _client() as c:
        r = await c.post("/expenses", json={"amount": "10", "description": "كهرباء"}, headers=mgr)
        assert r.status_code == 201, r.text
        assert r.json()["date"] == "2030-05-01"
        await _sql(env, "INSERT INTO accounting_periods (id, tenant_id, month, status) VALUES (:id, :t, '2030-05', 'closed')",
                   id=uuid.uuid4(), t=t)
        r = await c.post("/expenses", json={"amount": "10", "description": "كهرباء"}, headers=mgr)
        assert r.status_code == 400 and "2030-05" in r.json()["detail"]


# ── FIN-15 ─────────────────────────────────────────────────────────────────────────────────────

async def test_a_rejected_expense_is_closed():
    """Fails on the old code: a rejected expense could be approved later (and paid), or edited."""
    env = await _scenario()
    mgr = _auth(env["users"]["manager"], env["tenant_id"])
    async with _client() as c:
        e = (await c.post("/expenses", json={"amount": "25", "description": "صيانة"}, headers=mgr)).json()
        r = await c.post(f"/expenses/{e['id']}/approve", json={"approved": False}, headers=mgr)
        assert r.status_code == 200 and r.json()["status"] == "rejected"
        for body in ({"approved": True, "safe_id": str(env["safe_id"])}, {"approved": False}):
            r = await c.post(f"/expenses/{e['id']}/approve", json=body, headers=mgr)
            assert r.status_code == 409, body
        assert (await c.put(f"/expenses/{e['id']}", json={"amount": "30"}, headers=mgr)).status_code == 409
        assert (await c.put(f"/expenses/{e['id']}", json={"notes": "رُفض"}, headers=mgr)).status_code == 200
        assert (await c.post(f"/expenses/{e['id']}/cancel", json={}, headers=mgr)).status_code == 409
        assert (await c.delete(f"/expenses/{e['id']}", headers=mgr)).status_code == 204
    balance = (await _sql(env, "SELECT balance FROM safes WHERE id = :id", id=env["safe_id"]))[0][0]
    assert balance == 1000  # nothing was paid


async def test_a_category_in_use_is_stopped_and_keeps_its_movements():
    """Fails on the old code: drawer movements' foreign key clears on delete, so the category was
    deleted and the movements lost it."""
    env = await _scenario()
    mgr = _auth(env["users"]["manager"], env["tenant_id"])
    async with _client() as c:
        used = (await c.post("/financial-categories", json={"name": "ضيافة", "type": "expense"}, headers=mgr)).json()
        unused = (await c.post("/financial-categories", json={"name": "مؤقت", "type": "expense"}, headers=mgr)).json()
        async with AsyncSessionLocal() as s:
            tx = await pos_service.add_transaction(s, env["shift_id"], DrawerTxType.expense, 5, env["cashier_id"],
                                                   note="ضيافة", category_id=uuid.UUID(used["id"]))
        assert (await c.delete(f"/financial-categories/{used['id']}", headers=mgr)).status_code == 204
        assert (await c.delete(f"/financial-categories/{unused['id']}", headers=mgr)).status_code == 204
    rows = {str(r[0]): r[1] for r in await _sql(env, "SELECT id, is_active FROM financial_categories WHERE id = ANY(:ids)",
                                               ids=[uuid.UUID(used["id"]), uuid.UUID(unused["id"])])}
    assert rows == {used["id"]: False}
    kept = (await _sql(env, "SELECT category_id FROM drawer_transactions WHERE id = :id", id=tx.id))[0][0]
    assert str(kept) == used["id"]


# ── CON-7 ──────────────────────────────────────────────────────────────────────────────────────

async def test_new_customers_get_the_default_credit_limit():
    """Fails on the old code: the setting was declared in the manifest and never read."""
    env = await _scenario()
    t, cashier = env["tenant_id"], _auth(env["users"]["cashier"], env["tenant_id"])
    async with _client() as c:
        r = await c.post("/customers", json={"name": "بلا إعداد"}, headers=cashier)
        assert r.status_code == 200 and r.json()["credit_limit"] is None  # the manifest's default: 0, no limit
        await _sql(env, "INSERT INTO store_settings (id, tenant_id, key, value) VALUES (:id, :t, 'mod_settings_contacts', :v)",
                   id=uuid.uuid4(), t=t, v=json.dumps({"default_credit_limit": 5000}))
        r = await c.post("/customers", json={"name": "عميل جديد"}, headers=cashier)
        assert float(r.json()["credit_limit"]) == 5000
        r = await c.post("/customers", json={"name": "بلا حد", "credit_limit": None}, headers=cashier)
        assert r.json()["credit_limit"] is None
        r = await c.post("/customers", json={"name": "حد خاص", "credit_limit": "750"}, headers=cashier)
        assert float(r.json()["credit_limit"]) == 750


async def test_two_workspaces_save_the_same_hr_setting():
    """Fails on a database built from the baseline before v102: hr_settings' key was its primary key
    across workspaces, so the second workspace's save was a 500."""
    a, b = await _scenario(), await _scenario()
    async with _client() as c:
        for env in (a, b):
            r = await c.put("/hr/settings", json={"settings": {"days_in_month": 26}},
                            headers=_auth(env["users"]["manager"], env["tenant_id"]))
            assert r.status_code == 200, r.text[:200]


async def test_customer_search_has_an_index():
    async with AsyncSessionLocal() as s:
        found = (await s.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'customers' "
            "AND indexname IN ('ix_customers_name_trgm', 'ix_customers_name_lower')"))).scalars().all()
    assert found, "migration v102_b_platform: no index for the customer name search"


# ── ACC-3 ──────────────────────────────────────────────────────────────────────────────────────

async def test_accounting_reports_keep_a_branch_user_to_their_branches():
    """Fails on the old code: a holder of accounting:view limited to one branch read the whole
    company's books, and any other branch."""
    env = await _scenario(accounting=True)
    t, wh1, wh2 = env["tenant_id"], env["warehouse_id"], env["warehouse2_id"]
    viewer = _auth(await _user(env, ["accounting:view"], [wh1]), t)
    two = _auth(await _user(env, ["accounting:view"], [wh1, wh2]), t)
    mgr = _auth(env["users"]["manager"], t)
    async with _client() as c:
        mine = await c.get("/accounting/trial-balance", headers=viewer)
        assert mine.status_code == 200, mine.text
        branch1 = (await c.get("/accounting/trial-balance", params={"warehouse_id": str(wh1)}, headers=mgr)).json()
        company = (await c.get("/accounting/trial-balance", headers=mgr)).json()
        assert mine.json()["totals"] == branch1["totals"] != company["totals"]
        for path in ("/accounting/trial-balance", "/accounting/income-statement", "/accounting/balance-sheet"):
            assert (await c.get(path, params={"warehouse_id": str(wh2)}, headers=viewer)).status_code == 403, path
            assert (await c.get(path, params={"warehouse_id": str(uuid.uuid4())}, headers=viewer)).status_code == 404, path
            assert (await c.get(path, headers=two)).status_code == 403, path  # two branches: pick one
            assert (await c.get(path, params={"warehouse_id": str(wh2)}, headers=two)).status_code == 200, path
        party = f"/accounting/party-statement/customer/{env['customer_id']}"
        assert (await c.get(party, params={"warehouse_id": str(wh2)}, headers=viewer)).status_code == 403
        for path in ("/accounting/entries", "/accounting/vat-report", "/accounting/reconciliation"):
            assert (await c.get(path, headers=viewer)).status_code == 403, path
            assert (await c.get(path, headers=mgr)).status_code == 200, path


async def test_account_numbers_groups_and_the_party_picker():
    """Fails on the old code: a used number was a 400 (a race, a 500), a group stopped with live
    accounts under it, and there was no server-side party search."""
    env = await _scenario(accounting=True)
    t = env["tenant_id"]
    admin = _auth(env["cashier_id"], t)
    async with _client() as c:
        await c.get("/accounting/accounts", headers=admin)  # the chart is copied
        parent, code = (await _sql(env, "SELECT id, code FROM acc_accounts WHERE is_group AND type = 'expense' "
                                        "ORDER BY code LIMIT 1"))[0]
        r = await c.post("/accounting/accounts", json={"parent_id": str(parent), "name": "مكرر", "code": code}, headers=admin)
        assert r.status_code == 409
        group = (await c.post("/accounting/accounts", json={"parent_id": str(parent), "name": "مجموعة", "code": f"{code}G",
                                                            "is_group": True}, headers=admin)).json()
        child = (await c.post("/accounting/accounts", json={"parent_id": group["id"], "name": "فرعي"}, headers=admin)).json()
        assert (await c.put(f"/accounting/accounts/{group['id']}", json={"active": False}, headers=admin)).status_code == 409
        assert (await c.put(f"/accounting/accounts/{child['id']}", json={"active": False}, headers=admin)).status_code == 200
        assert (await c.put(f"/accounting/accounts/{group['id']}", json={"active": False}, headers=admin)).status_code == 200
        assert (await c.put(f"/accounting/accounts/{child['id']}", json={"active": True}, headers=admin)).status_code == 409

        for name in ("ألفا للتجارة", "بيتا للتجارة", "جاما"):
            await c.post("/customers", json={"name": name}, headers=admin)
        viewer = _auth(await _user(env, ["accounting:view"], [env["warehouse_id"]]), t)
        found = (await c.get("/accounting/parties", params={"type": "customer", "q": "للتجارة"}, headers=viewer)).json()
        assert [p["name"] for p in found] == ["ألفا للتجارة", "بيتا للتجارة"]
        one = (await c.get("/accounting/parties", params={"type": "customer", "q": "للتجارة", "limit": 1,
                                                          "id": str(env["customer_id"])}, headers=viewer)).json()
        assert [p["id"] for p in one] == [str(env["customer_id"]), found[0]["id"]]
        assert (await c.get("/accounting/parties", params={"type": "supplier"}, headers=viewer)).status_code == 200
        assert (await c.get("/accounting/parties", params={"type": "employee", "q": "x"}, headers=viewer)).status_code == 200
        assert (await c.get("/accounting/parties", params={"type": "robot"}, headers=viewer)).status_code == 422
        assert (await c.get("/accounting/parties", params={"type": "customer", "limit": 500}, headers=viewer)).status_code == 422
        cashier = _auth(env["users"]["cashier"], t)
        assert (await c.get("/accounting/parties", params={"type": "customer"}, headers=cashier)).status_code == 403


# ── REP-18 ─────────────────────────────────────────────────────────────────────────────────────

async def test_the_product_export_shows_costs_only_with_the_finance_permission():
    import io

    import openpyxl

    env = await _scenario()
    store = await _user(env, ["inventory"], [env["warehouse_id"]])
    async with _client() as c:
        plain = await c.get("/export/products", headers=_auth(store, env["tenant_id"]))
        full = await c.get("/export/products", headers=_auth(env["users"]["manager"], env["tenant_id"]))
    heads = [[cell.value for cell in openpyxl.load_workbook(io.BytesIO(r.content)).active[1]] for r in (plain, full)]
    assert "سعر التكلفة" not in heads[0] and "سعر التكلفة" in heads[1]
