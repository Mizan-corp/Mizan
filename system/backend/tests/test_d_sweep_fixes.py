"""What the route security sweep found (phase D), one test each.

- Modules' settings hold secrets (the WhatsApp access token): they were readable by every signed-in
  user through GET /modules/{id}/settings and GET /settings.
- POST /notifications/create let anyone send colleagues a notice with any title and link.
- GET /customers gave balances and credit limits to every signed-in user.
- The receipt printer's settings could be changed by anyone; its test print was a 500.
- GET /billing/subscription (Mizan's invoices to the workspace) and the WhatsApp message log
  (customers' phone numbers) needed a sign-in only; wipe-demo checked the role's name.
- The restaurant and consulting demo data had fixed primary keys: every workspace but the first got
  a 500 on those screens.
- A batch's trace and a product's stock breakdown answered 200 for an unknown id.
- The clinic: an invoice or claim for an unknown patient, and a patient field longer than its
  column, were 500s.
- What the database refuses (an unknown id, a text too long) is a 4xx with an Arabic message, not
  a 500 (factory.database_refused_input).
"""
import json
import os
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app
from app.activities.general.modules.contacts.models.party import Customer
from app.db.base import AsyncSessionLocal
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from tests.test_route_security_sweep import _user, _workspace

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _sql(tid, sql: str, **params):
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, tid)
        await s.execute(text(sql), params)
        await s.commit()
    current_tenant_id.set(None)


async def test_module_settings_and_their_secrets_need_the_settings_permission():
    tid = await _workspace()
    admin, cashier = await _user(tid, "admin"), await _user(tid, "cashier")
    secret = "EAAG-" + uuid.uuid4().hex
    await _sql(tid, "INSERT INTO store_settings (id, tenant_id, key, value) VALUES (:i, :t, 'mod_settings_whatsapp_gateway', :v)",
               i=uuid.uuid4(), t=tid, v=json.dumps({"whatsapp_api_token": secret}))
    async with _client() as c:
        r = await c.get("/modules/whatsapp_gateway/settings", headers=cashier)
        assert r.status_code == 403 and secret not in r.text
        r = await c.get("/settings", headers=cashier)
        assert r.status_code == 200 and secret not in r.text and "mod_settings_whatsapp_gateway" not in r.json()
        r = await c.get("/modules/whatsapp_gateway/settings", headers=admin)
        assert r.status_code == 200 and r.json()["values"]["whatsapp_api_token"] == secret


async def test_sending_a_notification_by_hand_needs_settings():
    tid = await _workspace()
    admin, cashier = await _user(tid, "admin"), await _user(tid, "cashier")
    body = {"title": "تحديث الحساب", "body": "ادخل هنا", "link": "https://evil.example/login"}
    async with _client() as c:
        assert (await c.post("/notifications/create", headers=cashier, json=body)).status_code == 403
        assert (await c.post("/notifications/create", headers=admin, json=body)).status_code == 200


async def test_the_customer_picker_shows_balances_only_to_who_works_with_customers():
    tid = await _workspace()
    cashier = await _user(tid, "cashier")
    clerk = await _user(tid, "cashier", ["payroll"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, tid)
        s.add(Customer(name="عميل مدين", phone="01000000000", balance=Decimal("1234"), credit_limit=Decimal("5000")))
        await s.commit()
    current_tenant_id.set(None)
    async with _client() as c:
        full = (await c.get("/customers", headers=cashier)).json()
        picker = (await c.get("/customers", headers=clerk)).json()
    assert float(full[0]["balance"]) == 1234 and float(full[0]["credit_limit"]) == 5000
    assert picker == [{"id": full[0]["id"], "name": "عميل مدين", "phone": "01000000000", "is_active": True}]


async def test_the_receipt_printer_settings_need_the_pos_and_its_test_print_works():
    tid = await _workspace()
    cashier, clerk = await _user(tid, "cashier"), await _user(tid, "cashier", ["payroll"])
    async with _client() as c:
        assert (await c.get("/modules/pos_hardware/config", headers=clerk)).status_code == 403
        assert (await c.put("/modules/pos_hardware/config", headers=clerk, json={"footer_note": "x"})).status_code == 403
        assert (await c.put("/modules/pos_hardware/config", headers=cashier, json={"footer_note": "شكرًا"})).status_code == 200
        r = await c.post("/modules/pos_hardware/test-print", headers=cashier, json={"paper_width": "58mm"})
        assert r.status_code == 200 and r.json()["paper_width"] == "58mm" and r.json()["cashier"] == "cashier"


async def test_subscription_message_log_and_wipe_demo_need_a_permission():
    tid = await _workspace()
    admin, clerk = await _user(tid, "admin"), await _user(tid, "cashier", ["payroll"])
    named_manager = await _user(tid, "manager", ["pos"])  # the role's name used to be enough
    async with _client() as c:
        assert (await c.get("/billing/subscription", headers=clerk)).status_code == 403
        assert (await c.get("/billing/subscription", headers=admin)).status_code == 200
        assert (await c.get("/integrations/whatsapp/messages", headers=clerk)).status_code == 403
        assert (await c.post("/integrations/whatsapp/send-receipt", headers=clerk,
                             json={"recipient_phone": "01000000000"})).status_code == 403
        assert (await c.get("/integrations/whatsapp/messages", headers=admin)).status_code == 200
        assert (await c.post("/platform/wipe-demo", headers=named_manager)).status_code == 403


async def test_restaurant_and_consulting_demo_data_reach_every_workspace():
    async with _client() as c:
        for _ in range(2):
            tid = await _workspace()
            admin = await _user(tid, "admin")
            for path in ("/modules/restaurant/recipes", "/modules/services/engagements", "/modules/services/timesheets"):
                r = await c.get(path, headers=admin)
                assert r.status_code == 200 and r.json(), (path, r.text)
            engagements = {e["id"] for e in (await c.get("/modules/services/engagements", headers=admin)).json()}
            sheets = (await c.get("/modules/services/timesheets", headers=admin)).json()
            sheets = sheets["sheets"]
            assert {s["engagement_id"] for s in sheets} <= engagements


async def test_unknown_ids_are_a_404():
    tid = await _workspace()
    admin = await _user(tid, "admin")
    async with _client() as c:
        assert (await c.get(f"/stock/balance/breakdown/{uuid.uuid4()}", headers=admin)).status_code == 404
        assert (await c.get(f"/modules/batches/{uuid.uuid4()}/trace", headers=admin)).status_code == 404


async def test_clinic_bills_only_its_own_patients_and_bounds_their_fields():
    tid = await _workspace()
    admin = await _user(tid, "admin")
    async with _client() as c:
        r = await c.post("/clinic/invoices", headers=admin, json={
            "patient_id": str(uuid.uuid4()), "patient_name": "x", "charges": [{"description": "كشف", "amount": 100}]})
        assert r.status_code == 404, r.text
        r = await c.post("/clinic/claims", headers=admin, json={
            "patient_id": str(uuid.uuid4()), "patient_name": "x", "insurance_provider": "x", "claimed_amount": 10})
        assert r.status_code == 404, r.text
        r = await c.post("/clinic/patients", headers=admin, json={
            "patient_mrn": "M" * 40, "full_name": "x", "national_id": "1", "phone": "1", "gender": "ذكر",
            "date_of_birth": "1990-01-01"})
        assert r.status_code == 422, r.text


async def test_what_the_database_refuses_is_a_4xx_not_a_500():
    tid = await _workspace()
    admin = await _user(tid, "admin")
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as c:
        # An activity prototype that doesn't check its references or lengths itself.
        r = await c.post("/agr/seasons", headers=admin, json={
            "plot_id": str(uuid.uuid4()), "season_code": "S1", "crop_name": "قمح", "variety": "x",
            "planting_date": "2026-01-01", "expected_harvest_date": "2026-05-01"})
        assert r.status_code == 400 and r.json()["detail"] == "أحد المعرّفات المرسلة غير موجود"
        r = await c.post("/logistics/drivers", headers=admin, json={
            "name": "x", "phone": "1" * 200, "national_id": "1", "license_expiry": "2030-01-01"})
        assert r.status_code == 400 and "أطول من المسموح" in r.json()["detail"]
        assert "SQL" not in r.text and "INSERT" not in r.text
