"""Sales, POS and stock operations ready for production, Phase B (PRODUCTION_READINESS: SAL-10,
SAL-12, POS-4, POS-5, POS-10, OPS-5, OPS-6, PLAT-6 for operations).

Each test failed on the code before this change:
- SAL-10: sales didn't declare pos, finance and contacts; installing it pulled only inventory.
- SAL-12: English answers; the invoice email could be sent without limit; the invoice PDF needed a
  sign-in only, from any branch.
- POS-4: a manager's password could be guessed without limit; only users.is_manager approved.
- POS-5: the drawer left for the next day could be negative or more than counted (a negative
  deposit); a drawer could be handed to anyone; the notes held raw ids.
- POS-10: English errors; reading a drawer needed a sign-in only.
- OPS-5: a retried dispatch moved stock twice; a dispatch couldn't be undone.
- OPS-6: one number sequence for every workspace; the list had no total or pages; totals could
  overflow the document's amount (a 500).
"""
import asyncio
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.activities.general.modules.pos import service as pos_service
from app.activities.general.modules.pos.models import Shift
from app.core.exceptions import NotFoundError
from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.auth.security import hash_password
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from app.platform.tenancy.models import Tenant
from tests.test_ready_sales_pos import PASSWORD, _body, _client, _env, _grant, _headers, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")

D = Decimal


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _user(env, role: str, *, manager: bool = False, branches=("wh",), name: str | None = None) -> dict:
    """Another user of env's workspace acting as `role`, assigned to `branches`."""
    uid = uuid.uuid4()
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tid"])
        s.add(User(id=uid, tenant_id=env["tid"], username=f"{role[:5]}_{uid.hex[:8]}", full_name=name or f"مستخدم {role}",
                   role=role, password_hash=hash_password(PASSWORD), is_active=True, is_manager=manager))
        await s.flush()
        for wh in branches:
            await s.execute(text("INSERT INTO user_warehouses (user_id, warehouse_id) VALUES (:u, :w)"),
                            {"u": uid, "w": env[wh]})
        await _grant(s, uid, env["tid"], role)
        await s.commit()
    current_tenant_id.set(None)
    return {"id": uid, "h": _headers(uid, env["tid"])}


# ── SAL-10 ────────────────────────────────────────────────────────────────────────────────────

async def test_installing_sales_brings_what_it_needs():
    from app.framework.activation import with_dependencies
    from app.framework.loader import manifest_index

    deps = manifest_index()["sales"]["dependencies"]
    assert {"core", "inventory", "contacts", "finance", "pos"} <= set(deps)
    assert {"finance", "contacts", "inventory"} <= set(manifest_index()["pos"]["dependencies"])
    assert {"pos", "finance", "contacts", "inventory", "core"} <= set(with_dependencies(["sales"]))

    env = await _env()
    async with AsyncSessionLocal() as s:
        tenant = await s.get(Tenant, env["tid"])
        tenant.active_modules = ["core"]
        await s.commit()
    async with _client() as c:
        r = await c.post("/modules/sales/toggle", json={"enabled": True}, headers=env["h"]["manager"])
        assert r.status_code == 200, r.text
        active = set(r.json()["active_modules"])
    assert {"sales", "pos", "finance", "contacts", "inventory"} <= active


# ── SAL-12 ────────────────────────────────────────────────────────────────────────────────────

async def test_sales_answers_in_arabic():
    env = await _env()
    async with _client() as c:
        sale = (await c.post("/sales", json=_body(env, notes="ملاحظة", local_id=str(uuid.uuid4())),
                             headers=env["h"]["cashier"])).json()
        assert sale["notes"] == "ملاحظة"  # the offline key is its own column, never in the notes
        r = await c.put(f"/sales/{sale['id']}/cancel", headers=env["h"]["cashier"])
        assert r.status_code == 403 and r.json()["detail"] == "ليس لديك صلاحية لهذه العملية"
        await c.post("/shifts/open", json={"warehouse_id": str(env["wh"]), "initial_amount": "0"}, headers=env["h"]["manager"])
        r = await c.put(f"/sales/{sale['id']}/cancel", headers=env["h"]["manager"])
        assert r.status_code == 200 and r.json()["detail"] == "تم إلغاء الفاتورة", r.text
        other = (await c.post("/sales", json=_body(env), headers=env["h"]["cashier"])).json()
        r = await c.post(f"/sales/{other['id']}/return", headers=env["h"]["cashier"])
        assert r.status_code == 200 and r.json()["detail"] == "تم إرجاع الفاتورة", r.text
    notes = await _sql(env, "SELECT notes FROM sales WHERE tenant_id = :t AND notes LIKE '%local_id%'", t=env["tid"])
    assert notes == []


async def test_the_invoice_email_is_rate_limited_and_the_pdf_needs_a_sales_permission(monkeypatch):
    from app.activities.general.modules.sales.services import invoices

    async def fake_render(db, invoice_id, tenant_id):
        return b"%PDF-", "application/pdf", "pdf", {"invoice_number": "INV-1", "created_at": None, "net_total": 0}

    async def fake_send(**_):
        return {"ok": True}

    monkeypatch.setattr(invoices, "render_file", fake_render)
    monkeypatch.setattr(invoices, "send_email", fake_send)
    env = await _env()
    store = await _user(env, "storekeeper")
    async with _client() as c:
        sale = (await c.post("/sales", json=_body(env), headers=env["h"]["cashier"])).json()
        url = f"/invoices/{sale['id']}/send"
        codes = [(await c.post(url, json={"email": "buyer@mizan.test"}, headers=env["h"]["cashier"])).status_code
                 for _ in range(11)]
        assert codes[:10] == [200] * 10 and codes[10] == 429, codes
        # Another user of the workspace isn't held up by the first one's limit.
        assert (await c.post(url, json={"email": "buyer@mizan.test"}, headers=env["h"]["manager"])).status_code == 200
        assert (await c.post(url, json={"email": "x" * 300 + "@a.co"}, headers=env["h"]["manager"])).status_code == 422
        # The PDF: a sales or POS permission, and the sale's branch.
        assert (await c.get(f"/invoices/{sale['id']}/pdf", headers=store["h"])).status_code == 403
        await c.post("/shifts/open", json={"warehouse_id": str(env["wh3"]), "initial_amount": "0"}, headers=env["h"]["manager"])
        far = (await c.post("/sales", json={**_body(env), "warehouse_id": str(env["wh3"])}, headers=env["h"]["manager"])).json()
        assert (await c.get(f"/invoices/{far['id']}/pdf", headers=env["h"]["cashier"])).status_code == 403
        assert (await c.get(f"/invoices/{uuid.uuid4()}/pdf", headers=env["h"]["cashier"])).status_code == 404
        assert (await c.get(f"/invoices/{sale['id']}/pdf", headers=env["h"]["cashier"])).status_code == 200


# ── POS-4 ─────────────────────────────────────────────────────────────────────────────────────

async def test_manager_passwords_are_locked_after_repeated_failures():
    env = await _env()
    url = f"/shifts/{env['shift']}/revenue-delivery"
    body = {"amount": "10", "safe_id": str(env["safe"]), "manager_id": str(env["manager"])}
    async with _client() as c:
        for _ in range(5):
            r = await c.post(url, json={**body, "manager_password": "wrong"}, headers=env["h"]["cashier"])
            assert r.status_code == 403 and r.json()["detail"] == "كلمة مرور المدير غير صحيحة"
        # Locked now, even with the right password, for this manager of the workspace…
        r = await c.post(url, json={**body, "manager_password": PASSWORD}, headers=env["h"]["cashier"])
        assert r.status_code == 429 and "إيقاف" in r.json()["detail"], r.text
        r = await c.post(url.replace(str(env["shift"]), str(env["shift2"])), json={**body, "manager_password": PASSWORD},
                         headers=env["h"]["cashier2"])
        assert r.status_code == 429
        # …and for the user who tried, whichever manager they name next.
        other = await _user(env, "manager", manager=True)
        r = await c.post(url, json={**body, "manager_id": str(other["id"]), "manager_password": PASSWORD},
                         headers=env["h"]["cashier"])
        assert r.status_code == 429
    # Another workspace's manager of the same id space is not affected.
    env2 = await _env()
    async with _client() as c:
        r = await c.post(f"/shifts/{env2['shift']}/revenue-delivery",
                         json={"amount": "10", "safe_id": str(env2["safe"]), "manager_id": str(env2["manager"]),
                               "manager_password": PASSWORD}, headers=env2["h"]["cashier"])
        assert r.status_code == 200, r.text


async def test_approval_rests_on_a_permission():
    env = await _env()
    # A manager by role (supervise) without the old flag approves; the flag on a role without
    # `shifts` or `supervise` doesn't; nor does a cashier.
    by_role = await _user(env, "manager", manager=False)
    flag_only = await _user(env, "storekeeper", manager=True)
    url = f"/shifts/{env['shift']}/revenue-delivery"
    body = {"amount": "10", "safe_id": str(env["safe"]), "manager_password": PASSWORD}
    async with _client() as c:
        r = await c.post(url, json={**body, "manager_id": str(flag_only["id"])}, headers=env["h"]["cashier"])
        assert r.status_code == 400 and r.json()["detail"] == pos_service.NOT_AN_APPROVER, r.text
        r = await c.post(url, json={**body, "manager_id": str(env["cashier2"])}, headers=env["h"]["cashier"])
        assert r.status_code == 400
        r = await c.post(url, json={**body, "manager_id": str(uuid.uuid4())}, headers=env["h"]["cashier"])
        assert r.status_code == 400
        r = await c.post(url, json={**body, "manager_id": str(by_role["id"])}, headers=env["h"]["cashier"])
        assert r.status_code == 200, r.text
        # Another workspace's manager approves nothing here.
        env2 = await _env()
        r = await c.post(url, json={**body, "manager_id": str(env2["manager"])}, headers=env["h"]["cashier"])
        assert r.status_code == 400


# ── POS-5 ─────────────────────────────────────────────────────────────────────────────────────

async def test_the_drawer_left_for_tomorrow_is_between_zero_and_the_count():
    env = await _env()
    async with _client() as c:
        url = f"/shifts/{env['shift']}/close"
        assert (await c.post(url, json={"closing_balance": "1000", "next_day_drawer": "-5"},
                             headers=env["h"]["cashier"])).status_code == 422
        r = await c.post(url, json={"closing_balance": "1000", "next_day_drawer": "1500"}, headers=env["h"]["cashier"])
        assert r.status_code == 400 and "أكبر من الرصيد الفعلي" in r.json()["detail"], r.text
        r = await c.post(f"/shifts/{env['shift2']}/close-with-manager",
                         json={"closing_balance": "500", "next_day_drawer": "800", "manager_id": str(env["manager"]),
                               "manager_password": PASSWORD}, headers=env["h"]["cashier2"])
        assert r.status_code == 400, r.text
        r = await c.post(f"/shifts/{env['shift2']}/close-with-manager",
                         json={"closing_balance": "500", "next_day_drawer": "200", "manager_id": str(env["manager"]),
                               "manager_password": PASSWORD}, headers=env["h"]["cashier2"])
        assert r.status_code == 200, r.text
        assert D(str(r.json()["deposit_amount"])) == D("300") and r.json()["deposit_received_by"] == str(env["manager"])
        r = await c.post(url, json={"closing_balance": "1000", "next_day_drawer": "400"}, headers=env["h"]["cashier"])
        assert r.status_code == 200 and D(str(r.json()["next_day_drawer"])) == D("400")
    rows = await _sql(env, "SELECT changes FROM audit_log WHERE entity_id = :s AND action = 'close_with_manager'", s=env["shift2"])
    assert len(rows) == 1 and rows[0].changes["approved_by"] == "manager"


async def test_a_drawer_is_handed_only_to_someone_who_can_take_it():
    env = await _env()
    far = await _user(env, "cashier", branches=("wh3",))
    store = await _user(env, "storekeeper")
    taker = await _user(env, "cashier", name="سارة")
    url = f"/shifts/{env['shift']}/transfer"
    async with _client() as c:
        for to, code in ((uuid.uuid4(), 404), (env["cashier"], 400), (store["id"], 400), (far["id"], 400),
                         (env["cashier2"], 400)):  # cashier2 already has an open shift here
            r = await c.post(url, json={"to_user_id": str(to), "amount": "900"}, headers=env["h"]["cashier"])
            assert r.status_code == code, (to, r.text)
        # The manager hands over the cashier's drawer: the document is the manager's, names not ids.
        r = await c.post(url, json={"to_user_id": str(taker["id"]), "amount": "900", "notes": "نهاية الدوام"},
                         headers=env["h"]["manager"])
        assert r.status_code == 200, r.text
        new = r.json()
    assert new["cashier_id"] == str(taker["id"]) and new["notes"] == "استلام عهدة من cashier"
    old = (await _sql(env, "SELECT notes, closed_by FROM shifts WHERE id = :s", s=env["shift"]))[0]
    assert old.notes == "تسليم عهدة إلى سارة — نهاية الدوام" and old.closed_by == env["manager"]
    doc = (await _sql(env, "SELECT created_by, metadata FROM archived_documents WHERE doc_type = 'shift_handover' "
                           "AND ref_id = :s", s=env["shift"]))[0]
    assert doc.created_by == env["manager"]
    assert doc.metadata["from_user_name"] == "cashier" and doc.metadata["to_user_name"] == "سارة"
    advances = await _sql(env, "SELECT note FROM hr_advances WHERE note LIKE 'فرق عجز%' AND note LIKE :id",
                          id=f"%{env['shift']}%")
    assert advances == []


# ── POS-10 ────────────────────────────────────────────────────────────────────────────────────

async def test_reading_a_drawer_needs_the_pos_or_shifts_permission():
    env = await _env()
    store = await _user(env, "storekeeper")
    async with _client() as c:
        for path in ("/shifts/current", "/shifts/last-drawer"):
            r = await c.get(path, params={"warehouse_id": str(env["wh"])}, headers=store["h"])
            assert r.status_code == 403, (path, r.text)
        assert (await c.get("/shifts/current", params={"warehouse_id": str(env["wh"])},
                            headers=env["h"]["cashier"])).status_code == 200
        # Someone else's drawer: managers and supervisors only; another branch: refused.
        assert (await c.get(f"/shifts/{env['shift']}/summary", headers=env["h"]["cashier2"])).status_code == 403
        assert (await c.get(f"/shifts/{env['shift']}/transactions", headers=env["h"]["cashier2"])).status_code == 403
        assert (await c.get(f"/shifts/{env['shift']}/summary", headers=env["h"]["manager"])).status_code == 200
        far = await _user(env, "cashier", branches=("wh3",))
        async with AsyncSessionLocal() as s:
            await bind_tenant(s, env["tid"])
            sid = uuid.uuid4()
            s.add(Shift(id=sid, tenant_id=env["tid"], cashier_id=far["id"], warehouse_id=env["wh"], status="open",
                        initial_amount=D("0"), started_at=datetime.now(UTC)))
            await s.commit()
        current_tenant_id.set(None)
        assert (await c.get(f"/shifts/{sid}/summary", headers=far["h"])).status_code == 403
        assert (await c.get(f"/shifts/{uuid.uuid4()}/summary", headers=env["h"]["manager"])).status_code == 404
    current_tenant_id.set(env["tid"])
    async with AsyncSessionLocal() as s:
        with pytest.raises(NotFoundError) as e:
            await pos_service.compute_summary(s, uuid.uuid4())
        assert e.value.detail == "الوردية غير موجودة"


# ── OPS-5 / OPS-6 ─────────────────────────────────────────────────────────────────────────────

def _dispatch(env, qty="3", **kw) -> dict:
    return {"from_warehouse_id": str(env["wh"]), "to_warehouse_id": str(env["wh2"]),
            "items": [{"product_id": str(env["product"]), "qty": qty}], **kw}


async def _qty(env, wh) -> Decimal:
    rows = await _sql(env, "SELECT qty FROM stock_balances WHERE product_id = :p AND warehouse_id = :w",
                      p=env["product"], w=env[wh])
    return rows[0].qty if rows else D("0")


async def test_a_retried_dispatch_moves_stock_once():
    env = await _env()
    h = env["h"]["manager"]
    cid = str(uuid.uuid4())
    async with _client() as c:
        a, b = await asyncio.gather(c.post("/operations/dispatch", json=_dispatch(env, client_id=cid), headers=h),
                                    c.post("/operations/dispatch", json=_dispatch(env, client_id=cid), headers=h))
        assert {a.status_code, b.status_code} <= {200, 409}, (a.text, b.text)
        again = await c.post("/operations/dispatch", json=_dispatch(env, client_id=cid), headers=h)
        assert again.status_code == 200
        first = a.json() if a.status_code == 200 else b.json()
        assert again.json()["doc_number"] == first["doc_number"]
        # The same key for another document is a mistake, not a retry.
        assert (await c.post("/operations/dispatch", json=_dispatch(env, qty="1", client_id=cid),
                             headers=h)).status_code == 422
        key = {"Idempotency-Key": f"req-{uuid.uuid4().hex}"}
        r1 = await c.post("/operations/stock-request", json=_dispatch(env), headers={**h, **key})
        r2 = await c.post("/operations/stock-request", json=_dispatch(env), headers={**h, **key})
        assert r1.status_code == r2.status_code == 200 and r1.json()["doc_number"] == r2.json()["doc_number"]
    assert await _qty(env, "wh") == D("47") and await _qty(env, "wh2") == D("53")
    docs = await _sql(env, "SELECT doc_type FROM archived_documents WHERE tenant_id = :t "
                           "AND doc_type IN ('dispatch_order', 'stock_request')", t=env["tid"])
    assert len(docs) == 2


async def test_cancelling_a_dispatch_moves_the_stock_back():
    env = await _env()
    store = await _user(env, "storekeeper", branches=("wh", "wh2"))
    async with _client() as c:
        d = (await c.post("/operations/dispatch", json=_dispatch(env, qty="5"), headers=store["h"])).json()
        assert await _qty(env, "wh") == D("45")
        assert (await c.post(f"/operations/{d['id']}/cancel", headers=store["h"])).status_code == 403
        assert (await c.post(f"/operations/{uuid.uuid4()}/cancel", headers=env["h"]["manager"])).status_code == 404
        r = await c.post(f"/operations/{d['id']}/cancel", json={"reason": "خطأ في الكمية"}, headers=env["h"]["manager"])
        assert r.status_code == 200 and r.json()["status"] == "cancelled", r.text
        assert (await c.post(f"/operations/{d['id']}/cancel", headers=env["h"]["manager"])).status_code == 400
        # A stock request is not a dispatch.
        req = (await c.post("/operations/stock-request", json=_dispatch(env), headers=store["h"])).json()
        assert (await c.post(f"/operations/{req['id']}/cancel", headers=env["h"]["manager"])).status_code == 404
        # What the destination no longer holds can't go back.
        d2 = (await c.post("/operations/dispatch", json=_dispatch(env, qty="2"), headers=store["h"])).json()
        await _sql(env, "UPDATE stock_balances SET qty = 1 WHERE product_id = :p AND warehouse_id = :w",
                   p=env["product"], w=env["wh2"])
        r = await c.post(f"/operations/{d2['id']}/cancel", headers=env["h"]["manager"])
        assert r.status_code == 400 and "لا يمكن إلغاء الإذن" in r.json()["detail"], r.text
        listed = (await c.get("/operations/", params={"doc_type": "dispatch_order"}, headers=store["h"])).json()
    assert {i["id"]: i["status"] for i in listed["items"]} == {d["id"]: "cancelled", d2["id"]: "done"}
    assert await _qty(env, "wh") == D("48")
    moves = await _sql(env, "SELECT movement_type, warehouse_id, qty FROM stock_movements WHERE ref_type = 'dispatch_cancel'")
    assert sorted((str(m.movement_type).split(".")[-1], m.warehouse_id, m.qty) for m in moves) == sorted(
        [("transfer_out", env["wh2"], D("5")), ("transfer_in", env["wh"], D("5"))])
    audit = await _sql(env, "SELECT 1 FROM audit_log WHERE entity_type = 'dispatch' AND action = 'cancel'")
    assert len(audit) == 1


async def test_operations_number_per_workspace_and_list_with_a_total():
    a, b = await _env(), await _env()
    async with _client() as c:
        for env in (a, b):
            r = await c.post("/operations/dispatch", json=_dispatch(env, qty="1"), headers=env["h"]["manager"])
            assert r.status_code == 200 and r.json()["doc_number"] == "DSP-000001", r.text
            r = await c.post("/operations/stock-request", json=_dispatch(env), headers=env["h"]["manager"])
            assert r.json()["doc_number"] == "REQ-000001"
        r = await c.post("/operations/dispatch", json=_dispatch(a, qty="1"), headers=a["h"]["manager"])
        assert r.json()["doc_number"] == "DSP-000002"
        page = (await c.get("/operations/", params={"page_size": 2}, headers=a["h"]["manager"])).json()
        assert page["total"] == 3 and page["pages"] == 2 and len(page["items"]) == 2
        second = (await c.get("/operations/", params={"page_size": 2, "page": 2}, headers=a["h"]["manager"])).json()
        assert len(second["items"]) == 1
        assert (await c.get("/operations/", params={"page_size": 500}, headers=a["h"]["manager"])).status_code == 422
        assert (await c.get("/operations/", params={"doc_type": "sale_invoice"}, headers=a["h"]["manager"])).status_code == 422


async def test_operation_documents_are_bounded():
    env = await _env()
    h = env["h"]["manager"]
    pid = str(env["product"])
    async with _client() as c:
        bad = [
            {**_dispatch(env), "items": []},
            {**_dispatch(env), "items": [{"product_id": pid, "qty": "1"}] * 501},
            _dispatch(env, qty="0"),
            _dispatch(env, qty="1.2345"),
            _dispatch(env, qty="1e12"),
            _dispatch(env, notes="x" * 1001),
            {**_dispatch(env), "items": [{"product_id": pid, "qty": "999999999"}] * 11},  # total over the document's
        ]
        for body in bad:
            for path in ("/operations/dispatch", "/operations/stock-request"):
                r = await c.post(path, json=body, headers=h)
                assert r.status_code == 422, (path, r.text[:200])
        r = await c.post("/operations/dispatch", json=_dispatch(env), headers={**h, "Idempotency-Key": "bad key!"})
        assert r.status_code == 400
