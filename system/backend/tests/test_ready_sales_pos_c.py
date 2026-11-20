"""Sales and POS ready for production, Phase C (PRODUCTION_READINESS: SAL-11, POS-6, POS-8).

Each test failed on the code before this change:
- SAL-11: the sales screen filtered quotations on the client after paging and had no total; its
  cards added gross totals (VAT and returns in); a quotation's money went only to a drawer, a safe
  or credit (no wallet); drafts couldn't be edited, and editing a quotation kept stale prices.
- POS-6: the shift summary counted a split sale whole under its first payment method.
- POS-8: cancelling a drawer row rested on the `is_manager` flag (no permission, no branch, no
  audit); the shifts screen had no way to list who can approve or take over a drawer.
"""
import json
import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.auth.security import hash_password
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from tests.test_ready_sales_ops_b import _user
from tests.test_ready_sales_pos import PASSWORD, _body, _client, _env, _headers, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")

D = Decimal


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _holder(env, grants: list[str], *, manager: bool = False, branches=("wh",)) -> dict:
    """A user of env's workspace acting as a role of the workspace holding exactly `grants`."""
    uid, rid = uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tid"])
        s.add(User(id=uid, tenant_id=env["tid"], username=f"u_{uid.hex[:10]}", full_name="حامل صلاحيات",
                   role="cashier", password_hash=hash_password(PASSWORD), is_active=True, is_manager=manager))
        await s.flush()
        for wh in branches:
            await s.execute(text("INSERT INTO user_warehouses (user_id, warehouse_id) VALUES (:u, :w)"),
                            {"u": uid, "w": env[wh]})
        await s.execute(text("INSERT INTO sys_roles (id, tenant_id, code, name, name_en, is_system, is_clinical, grants) "
                             "VALUES (:id, :t, :c, :c, :c, false, false, CAST(:g AS jsonb))"),
                        {"id": rid, "t": env["tid"], "c": f"ws-{rid.hex[:8]}", "g": json.dumps(grants)})
        await s.execute(text("INSERT INTO user_role_assignments (id, user_id, role_id, is_active, tenant_id) "
                             "VALUES (gen_random_uuid(), :u, :r, true, :t)"), {"u": uid, "r": rid, "t": env["tid"]})
        await s.execute(text("UPDATE users SET active_role_id = :r WHERE id = :u"), {"r": rid, "u": uid})
        await s.commit()
    current_tenant_id.set(None)
    return {"id": uid, "h": _headers(uid, env["tid"])}


async def _vat(env, registered: bool) -> None:
    for key, value in (("vat_registered", "true" if registered else "false"), ("prices_include_vat", "true")):
        await _sql(env, "INSERT INTO store_settings (id, tenant_id, key, value) VALUES (:i, :t, :k, :v) "
                        "ON CONFLICT (tenant_id, key) DO UPDATE SET value = EXCLUDED.value",
                   i=uuid.uuid4(), t=env["tid"], k=key, v=value)


# ── SAL-11: the list, its total and its figures ──────────────────────────────────────────────

async def test_the_sales_page_filters_on_the_server_and_gives_the_total():
    env = await _env()
    h = env["h"]["cashier"]
    async with _client() as c:
        for _ in range(3):
            assert (await c.post("/sales", json=_body(env), headers=h)).status_code == 200
        for _ in range(2):
            assert (await c.post("/sales/quotations", json=_body(env), headers=h)).status_code == 200
        assert (await c.post("/sales/draft", json=_body(env), headers=h)).status_code == 200

        r = await c.get("/sales/page", params={"kind": "quotations", "page_size": 2}, headers=h)
        assert r.status_code == 200, r.text
        page = r.json()
        assert page["total"] == 3 and len(page["items"]) == 2 and page["page"] == 1
        assert {i["status"] for i in page["items"]} <= {"quotation", "draft"}
        second = (await c.get("/sales/page", params={"kind": "quotations", "page_size": 2, "page": 2}, headers=h)).json()
        assert len(second["items"]) == 1 and second["total"] == 3
        invoices = (await c.get("/sales/page", params={"kind": "invoices"}, headers=h)).json()
        assert invoices["total"] == 3 and all(i["status"] == "confirmed" for i in invoices["items"])
        assert invoices["items"][0]["created_by_name"] == "cashier"
        assert (await c.get("/sales/page", params={"kind": "bogus"}, headers=h)).status_code == 422
        # The plain list still answers a list, with the same filters.
        listed = (await c.get("/sales", params={"kind": "quotations"}, headers=h)).json()
        assert isinstance(listed, list) and len(listed) == 3


async def test_the_summary_is_net_of_vat_and_returns():
    env = await _env()
    await _vat(env, True)
    h = env["h"]["cashier"]
    async with _client() as c:
        a = (await c.post("/sales", json=_body(env, qty=2), headers=h)).json()
        credit = (await c.post("/sales", json=_body(env, is_credit=True, customer_id=str(env["customer"]),
                                                    payment_method="credit"), headers=h))
        assert credit.status_code == 200, credit.text
        r = await c.post(f"/sales/{a['id']}/partial-return",
                         json={"items": [{"product_id": str(env["product"]), "qty": "1"}]}, headers=h)
        assert r.status_code == 200, r.text
        await c.post("/sales/quotations", json=_body(env), headers=h)
        summary = await c.get("/sales/summary", headers=h)
        assert summary.status_code == 200, summary.text
        got = summary.json()
    sold = await _sql(env, "SELECT COALESCE(SUM(net_total - tax_amount), 0) AS v, COALESCE(SUM(tax_amount), 0) AS tax "
                           "FROM sales WHERE status = 'confirmed'")
    back = await _sql(env, "SELECT COALESCE(SUM(net_total - tax_amount), 0) AS v FROM sales WHERE status = 'returned'")
    assert sold[0].tax > 0  # VAT-registered: the documents carry VAT
    assert D(got["gross_sales"]) == sold[0].v and D(got["returns_total"]) == back[0].v
    assert D(got["net_sales"]) == sold[0].v - back[0].v
    assert D(got["net_sales"]) < D("300")  # not the gross totals with VAT
    assert D(got["outstanding"]) == D("100.00")  # the credit sale, VAT included: what the customer owes
    assert (got["invoice_count"], got["returns_count"], got["quotation_count"], got["draft_count"]) == (2, 1, 1, 0)


# ── SAL-11: where a quotation's money goes ───────────────────────────────────────────────────

async def test_a_quotation_can_be_confirmed_into_a_wallet():
    env = await _env()
    h = env["h"]["manager"]  # no shift: a wallet needs none
    async with _client() as c:
        q = (await c.post("/sales/quotations", json=_body(env), headers=h)).json()
        r = await c.post(f"/sales/{q['id']}/confirm-quotation", json={"destination": "wallet"}, headers=h)
        assert r.status_code == 400 and r.json()["detail"] == "يجب اختيار المحفظة"
        r = await c.post(f"/sales/{q['id']}/confirm-quotation",
                         json={"destination": "wallet", "wallet_id": str(uuid.uuid4())}, headers=h)
        assert r.status_code == 404
        r = await c.post(f"/sales/{q['id']}/confirm-quotation",
                         json={"destination": "wallet", "wallet_id": str(env["wallet"])}, headers=h)
        assert r.status_code == 200, r.text
        sale = r.json()
    assert sale["status"] == "confirmed" and sale["payment_method"] == "wallet" and sale["wallet_id"] == str(env["wallet"])
    assert D(sale["paid_amount"]) == D("100")
    wallet = await _sql(env, "SELECT balance FROM payment_wallets WHERE id = :w", w=env["wallet"])
    assert wallet[0].balance == D("100.00")
    lines = await _sql(env, "SELECT method, amount, wallet_id FROM sale_payments WHERE sale_id = :s", s=uuid.UUID(sale["id"]))
    assert [(r.method, r.amount, r.wallet_id) for r in lines] == [("wallet", D("100.00"), env["wallet"])]


# ── SAL-11: editing drafts and quotations ────────────────────────────────────────────────────

async def test_drafts_and_quotations_are_edited_at_todays_prices_by_those_who_make_them():
    env = await _env()
    pos_only = await _holder(env, ["pos"])
    quotes_only = await _holder(env, ["quotations"])
    async with _client() as c:
        draft = (await c.post("/sales/draft", json=_body(env), headers=env["h"]["cashier"])).json()
        quote = (await c.post("/sales/quotations", json=_body(env), headers=env["h"]["cashier"])).json()
        await _sql(env, "UPDATE products SET retail_price = 120 WHERE id = :p", p=env["product"])

        # A line sent without a price takes the product's price now; a stale one is refused.
        line = {"product_id": str(env["product"]), "qty": "3"}
        r = await c.put(f"/sales/{draft['id']}", json={"items": [line], "notes": "معدلة"}, headers=pos_only["h"])
        assert r.status_code == 200, r.text
        r = await c.put(f"/sales/{quote['id']}", json={"items": [{**line, "unit_price": "100"}]},
                        headers=quotes_only["h"])
        assert r.status_code == 400 and "120.00" in r.json()["detail"], r.text
        r = await c.put(f"/sales/{quote['id']}", json={"items": [line]}, headers=quotes_only["h"])
        assert r.status_code == 200, r.text

        # Each document by those who make it: a POS user edits drafts, not quotations, and back.
        assert (await c.put(f"/sales/{quote['id']}", json={"notes": "x"}, headers=pos_only["h"])).status_code == 403
        assert (await c.put(f"/sales/{draft['id']}", json={"notes": "x"}, headers=quotes_only["h"])).status_code == 403
        assert (await c.delete(f"/sales/{quote['id']}", headers=pos_only["h"])).status_code == 403

        got = (await c.get(f"/sales/{draft['id']}", headers=env["h"]["cashier"])).json()
        assert D(str(got["net_total"])) == D("360") and got["notes"] == "معدلة"
        assert D(str(got["items"][0]["unit_price"])) == D("120")

        # A confirmed sale is never edited.
        sale = (await c.post("/sales", json=_body(env, price="120"), headers=env["h"]["cashier"])).json()
        r = await c.put(f"/sales/{sale['id']}", json={"notes": "x"}, headers=env["h"]["cashier"])
        assert r.status_code == 400

        assert (await c.delete(f"/sales/{draft['id']}", headers=pos_only["h"])).status_code == 204
        assert (await c.delete(f"/sales/{quote['id']}", headers=quotes_only["h"])).status_code == 204
    audit = await _sql(env, "SELECT action FROM audit_log WHERE entity_id = :s ORDER BY created_at", s=uuid.UUID(draft["id"]))
    assert [a.action for a in audit][-2:] == ["update_draft", "delete"]


# ── POS-6 ─────────────────────────────────────────────────────────────────────────────────────

async def test_the_shift_summary_counts_each_part_of_a_split_payment():
    env = await _env()
    h = env["h"]["cashier"]
    async with _client() as c:
        r = await c.post("/sales", json=_body(env, payments=[{"method": "cash", "amount": "60"},
                                                             {"method": "wallet", "amount": "40",
                                                              "wallet_id": str(env["wallet"])}]), headers=h)
        assert r.status_code == 200, r.text
        assert (await c.post("/sales", json=_body(env), headers=h)).status_code == 200
        summary = (await c.get(f"/shifts/{env['shift']}/summary", headers=h)).json()
    by = {p["method"]: p for p in summary["payment_breakdown"]}
    assert D(str(by["cash"]["total"])) == D("160") and by["cash"]["count"] == 2
    assert D(str(by["wallet"]["total"])) == D("40") and by["wallet"]["count"] == 1
    assert by["wallet"]["wallet_name"] == "محفظة"
    assert D(str(summary["wallet_total"])) == D("40")
    assert D(str(summary["expected_balance"])) == D("1160")


# ── POS-8 ─────────────────────────────────────────────────────────────────────────────────────

async def test_cancelling_a_drawer_row_needs_an_approver_and_is_audited():
    env = await _env()
    supervisor = await _user(env, "manager", manager=False)  # supervise by role, no manager flag
    flag_only = await _holder(env, ["pos"], manager=True)  # the old flag without shifts or supervise
    async with _client() as c:
        rows = []
        for _ in range(2):
            r = await c.post(f"/shifts/{env['shift']}/transactions", json={"type": "expense", "amount": "15"},
                             headers=env["h"]["cashier"])
            assert r.status_code == 200, r.text
            rows.append(r.json()["id"])
        for h in (env["h"]["cashier"], env["h"]["cashier2"], flag_only["h"]):
            assert (await c.delete(f"/shifts/transactions/{rows[0]}", headers=h)).status_code == 403
        assert (await c.delete(f"/shifts/transactions/{uuid.uuid4()}", headers=supervisor["h"])).status_code == 404
        r = await c.delete(f"/shifts/transactions/{rows[0]}", headers=supervisor["h"])
        assert r.status_code == 204, r.text
        assert (await c.delete(f"/shifts/transactions/{rows[1]}", headers=env["h"]["manager"])).status_code == 204
        summary = (await c.get(f"/shifts/{env['shift']}/summary", headers=env["h"]["cashier"])).json()
        assert D(str(summary["expenses_total"])) == D("0")
    audit = await _sql(env, "SELECT user_id, changes FROM audit_log WHERE entity_id = :s AND action = 'cancel_drawer_tx' "
                            "ORDER BY created_at", s=env["shift"])
    assert [a.user_id for a in audit] == [supervisor["id"], env["manager"]]
    assert audit[0].changes["tx_id"] == rows[0]


async def test_the_shifts_screen_lists_approvers_and_who_can_take_the_drawer():
    env = await _env()
    taker = await _user(env, "cashier", name="سارة")
    far = await _user(env, "cashier", branches=("wh3",))
    store = await _user(env, "storekeeper")
    async with _client() as c:
        r = await c.get(f"/shifts/{env['shift']}/people", headers=env["h"]["cashier"])
        assert r.status_code == 200, r.text
        people = r.json()
        # Someone else's shift: managers and supervisors only.
        assert (await c.get(f"/shifts/{env['shift']}/people", headers=env["h"]["cashier2"])).status_code == 403
        assert (await c.get(f"/shifts/{uuid.uuid4()}/people", headers=env["h"]["manager"])).status_code == 404
    approvers = {p["id"] for p in people["approvers"]}
    receivers = {p["id"] for p in people["receivers"]}
    assert approvers == {str(env["manager"])}
    assert str(taker["id"]) in receivers and str(env["manager"]) in receivers
    # Not the shift's own cashier, not one with an open shift here, not another branch's, not a storekeeper.
    assert not receivers & {str(env["cashier"]), str(env["cashier2"]), str(far["id"]), str(store["id"])}
