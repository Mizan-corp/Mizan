"""HR, phase C (PRODUCTION_READINESS.md, `hr`).

HR-9  advances the month's pay can't cover are carried to the next month as an open advance (not
      dropped); the ledger recovers only what was deducted; reopening takes the carry back.
HR-12 the rules that were fixed (weekend day, day rollover, paid leave days, the default shift) are
      typed settings with today's values as defaults; the employee's chosen shift counts; money is
      Decimal.
HR-15 the lists the screens page (attendance, advances, audit log) are paged; shifts can be edited and
      stopped; stopped employees can be listed; a shift that isn't the workspace's is a 404.
"""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.platform.tenancy.context import current_tenant_id
from tests.test_hr_ready import MONTH, _attend, _client, _headers, _scalar, _session, _workspace

pytestmark = pytest.mark.skipif(not __import__("os").environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

D = Decimal
NEXT = "2025-03"


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _advances_balance(db, employee_id) -> Decimal:
    """The employee's balance in the ledger's employee advances account (what they still owe)."""
    return await _scalar(db, """
        SELECT COALESCE(SUM(l.debit - l.credit), 0) FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id
        WHERE a.role = 'employee_advances' AND l.party_id = :e
    """, e=employee_id)


# ── HR-9 ─────────────────────────────────────────────────────────────────────────────────────

async def test_an_advance_the_pay_cant_cover_is_carried_to_the_next_month():
    """Old code: four days' pay (400) less an advance of 1000 was clamped at 0 and the other 600 of
    the advance were dropped: nothing deducted them later, and the ledger booked all 1000 as recovered."""
    from app.activities.general.modules.hr.routes import hr as routes
    from app.activities.general.modules.hr.schemas import AdvanceCreate
    from app.activities.general.modules.hr.services import payroll

    ws = await _workspace()
    emp = ws["emps"][0]
    db, user = await _session(ws)
    async with db:
        for day in (2, 3, 4, 5):  # 4 × 8 hours of 26 × 8: base pay 400
            await _attend(db, emp, day)
        await db.commit()
        await routes.add_advance(AdvanceCreate(employee_id=emp, amount=D("1000"), date=date(2025, 2, 6),
                                               safe_id=ws["safe_id"]), db=db, current_user=user)
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        entry = (await db.execute(text("SELECT id, base_pay, advances, advances_carried, net_salary FROM hr_payroll_entries "
                                       "WHERE employee_id = :e"), {"e": emp})).one()
        assert (entry.base_pay, entry.advances, entry.net_salary, entry.advances_carried) == (
            D("400.00"), D("1000.00"), D("0.00"), D("600.00"))

        # A bonus raises what the month can deduct: less is carried.
        from app.activities.general.modules.hr.schemas import PayrollUpdate
        r = await routes.update_payroll(entry.id, PayrollUpdate(bonus=D("100")), db=db, current_user=user)
        assert r["net_salary"] == 0.0
        assert await _scalar(db, "SELECT advances_carried FROM hr_payroll_entries WHERE id = :i", i=entry.id) == D("500.00")

        await payroll.submit_payroll_period(db, MONTH, str(user.id))
        await payroll.approve_payroll_period(db, MONTH, str(user.id))
        carried = (await db.execute(text("""
            SELECT id, amount, date, record_type, status, safe_id, wallet_id FROM hr_advances
            WHERE employee_id = :e AND carried_from_period_id IS NOT NULL
        """), {"e": emp})).one()
        assert (carried.amount, carried.date, carried.record_type, carried.status) == (D("500.00"), date(2025, 3, 1), "سلفة", "active")
        assert carried.safe_id is None and carried.wallet_id is None  # no cash moved again
        assert await _scalar(db, "SELECT balance FROM safes WHERE id = :s", s=ws["safe_id"]) == D("9000.00")
        # The ledger recovered only the 500 deducted: 500 of the advance is still owed.
        assert await _advances_balance(db, emp) == D("500.00")

        # The next month deducts it.
        assert (await payroll.load_hr_records_for_month(db, emp, NEXT))["advance"] == D("500.00")
        # It is cancelled only by reopening the month it came from.
        with pytest.raises(HTTPException) as e:
            await routes.cancel_advance(carried.id, None, db=db, current_user=user)
        assert e.value.status_code == 409
        await db.rollback()

        await payroll.reopen_payroll_period(db, MONTH, str(user.id))
        assert await _scalar(db, "SELECT status FROM hr_advances WHERE id = :i", i=carried.id) == "cancelled"
        assert (await payroll.load_hr_records_for_month(db, emp, NEXT))["advance"] == 0
        assert await _advances_balance(db, emp) == D("1000.00")  # the approval was reversed

        # Approved again: carried again, once.
        await payroll.submit_payroll_period(db, MONTH, str(user.id))
        await payroll.approve_payroll_period(db, MONTH, str(user.id))
        assert await _scalar(db, "SELECT count(*) FROM hr_advances WHERE employee_id = :e AND carried_from_period_id IS NOT NULL "
                                 "AND status = 'active'", e=emp) == 1

        # The next month, approved, holds the carry: the month it came from can't be reopened under it.
        await payroll.calculate_payroll_month(db, NEXT, str(user.id))
        nxt = await _scalar(db, "SELECT advances FROM hr_payroll_entries pe JOIN hr_payroll_periods p ON p.id = pe.period_id "
                                "WHERE p.month = :m AND pe.employee_id = :e", m=NEXT, e=emp)
        assert nxt == D("500.00")
        await payroll.submit_payroll_period(db, NEXT, str(user.id))
        await payroll.approve_payroll_period(db, NEXT, str(user.id))
        with pytest.raises(HTTPException) as e:
            await payroll.reopen_payroll_period(db, MONTH, str(user.id))
        assert e.value.status_code == 409
        await db.rollback()


async def test_settle_splits_the_advances_between_this_month_and_the_next():
    from app.activities.general.modules.hr.services.payroll import settle

    parts = dict(base_pay=D("400"), lateness_deduction=D("50"), deductions=D("0"), overtime_pay=D("0"),
                 bonus_payment=D("0"), bonus=D("0"))
    assert settle(advances=D("100"), **parts) == (D("250.00"), D("0.00"))
    assert settle(advances=D("1000"), **parts) == (D("0.00"), D("650.00"))
    # Deductions beyond the pay: nothing of the advance is deducted, all of it is carried.
    assert settle(advances=D("300"), **{**parts, "deductions": D("500")}) == (D("0.00"), D("300.00"))


# ── HR-12 ────────────────────────────────────────────────────────────────────────────────────

def _day(result, iso):
    return next(d for d in result["daily_breakdown"] if d["date"] == iso)


def test_the_fixed_rules_are_settings_with_todays_values_as_defaults():
    """Old code: Friday weekend, 5 am rollover, 4 paid leave days and a 9-21 shift were fixed, and
    money came back as float."""
    from app.activities.general.modules.hr.services.payroll_engine import calculate_payroll, effective_settings

    defaults = effective_settings({})
    assert (defaults["weekend_day"], defaults["day_start_hour"], defaults["paid_leave_days"], defaults["days_in_month"],
            defaults["default_shift_start_hour"], defaults["default_shift_end_hour"]) == (4, 5, 4, 26, 9, 21)
    assert effective_settings({"weekend_day": "x", "paid_leave_days": "-3"})["weekend_day"] == 4

    emp = {"monthly_salary": "2600", "shift_schedule": ""}
    feb = lambda d, h, m=0: datetime(2025, 2, d, h, m, tzinfo=UTC)  # noqa: E731
    leave = [{"check_in": feb(d, 9), "check_out": feb(d, 21), "status": "leave"} for d in (3, 4)]
    night = [{"check_in": feb(10, 4, 30), "check_out": feb(10, 6), "status": "present"}]

    base = calculate_payroll(emp, leave + night, {}, {}, month=MONTH)
    assert _day(base, "2025-02-07")["status"] == "weekend"  # a Friday
    assert _day(base, "2025-02-08")["status"] == "absent"
    assert "إجازة مدفوعة" in _day(base, "2025-02-04")["note"]
    assert _day(base, "2025-02-09")["status"] == "present"  # 04:30 on the 10th belongs to the 9th
    assert isinstance(base["net_salary"], Decimal) and isinstance(base["hourly_rate"], Decimal)
    assert base["shift_length"] == 12 and base["hourly_rate"] == D("8.3333")  # 2600 / (26 × 12)

    cfg = {"weekend_day": "5", "paid_leave_days": "1", "day_start_hour": "4", "default_shift_start_hour": "8",
           "default_shift_end_hour": "16", "days_in_month": "25"}
    changed = calculate_payroll(emp, leave + night, cfg, {}, month=MONTH)
    assert _day(changed, "2025-02-07")["status"] == "absent"
    assert _day(changed, "2025-02-08")["status"] == "weekend"  # Saturday
    assert "إجازة مدفوعة" in _day(changed, "2025-02-03")["note"] and "تجاوز" in _day(changed, "2025-02-04")["note"]
    assert _day(changed, "2025-02-10")["status"] == "present"  # 04:30 is after a 4 am day start
    assert changed["shift_length"] == 8 and changed["hourly_rate"] == D("13.0000")  # 2600 / (25 × 8)

    # The shift chosen from the list wins over the typed schedule.
    shifts = {"77": {"id": "77", "name": "صباحي", "start_time": "07:00", "end_time": "13:00"}}
    chosen = calculate_payroll({**emp, "shift_id": "77", "shift_schedule": "09:00-21:00"}, [], {}, shifts, month=MONTH)
    assert chosen["shift_length"] == 6


async def test_settings_are_typed_and_saved():
    ws = await _workspace()
    h = _headers(ws, "admin")
    async with _client() as c:
        r = await c.put("/hr/settings", headers=h, json={"settings": {"weekend_day": 5, "paid_leave_days": 2}})
        assert r.status_code == 200 and (r.json()["weekend_day"], r.json()["paid_leave_days"]) == (5, 2)
        assert (await c.put("/hr/settings", headers=h, json={"settings": {"weekend_day": 7}})).status_code == 422
        assert (await c.put("/hr/settings", headers=h, json={"settings": {"day_start_hour": 13}})).status_code == 422
        assert (await c.get("/hr/settings", headers=h)).json()["weekend_day"] == 5


# ── HR-15 ────────────────────────────────────────────────────────────────────────────────────

async def test_the_lists_are_paged():
    """Old code: every attendance day and advance came back at once (the screen cut them at 100/60)."""
    ws = await _workspace()
    db, _ = await _session(ws)
    async with db:
        for day in range(1, 29):
            for emp in ws["emps"]:
                await _attend(db, emp, day)
        for i in range(3):
            await db.execute(text("INSERT INTO hr_advances (id, tenant_id, employee_id, amount, date, record_type) "
                                  "VALUES (:id, :t, :e, 10, :d, 'خصم')"),
                             {"id": uuid.uuid4(), "t": ws["tid"], "e": ws["emps"][0], "d": date(2025, 2, 10 + i)})
        await db.commit()
    h = _headers(ws, "admin")
    async with _client() as c:
        first = (await c.get("/hr/attendance", params={"month": MONTH, "page_size": 50}, headers=h)).json()
        assert first["total"] == 56 and len(first["items"]) == 50 and first["items"][0]["work_date"] == "2025-02-28"
        last = (await c.get("/hr/attendance", params={"month": MONTH, "page": 2, "page_size": 50}, headers=h)).json()
        assert len(last["items"]) == 6 and {i["id"] for i in last["items"]}.isdisjoint({i["id"] for i in first["items"]})
        adv = (await c.get("/hr/advances", params={"page_size": 2}, headers=h)).json()
        assert adv["total"] == 3 and len(adv["items"]) == 2 and adv["items"][0]["date"] == "2025-02-12"
        assert (await c.get("/hr/advances", params={"month": "2025-01"}, headers=h)).json()["total"] == 0
        assert (await c.get("/hr/attendance", params={"page_size": 500}, headers=h)).status_code == 422
        log = (await c.get("/hr/audit-log", params={"page_size": 5}, headers=h)).json()
        assert set(log) == {"items", "total", "page", "page_size"}


async def test_shifts_and_employees_can_be_edited_and_stopped():
    ws = await _workspace()
    h = _headers(ws, "admin")
    emp = str(ws["emps"][0])
    async with _client() as c:
        s = (await c.post("/hr/shifts", headers=h, json={"name": "صباحي", "start_time": "08:00", "end_time": "16:00"})).json()
        r = await c.put(f"/hr/shifts/{s['id']}", headers=h, json={"end_time": "15:00"})
        assert r.status_code == 200 and (r.json()["name"], r.json()["end_time"]) == ("صباحي", "15:00")
        assert (await c.put("/hr/shifts/nope", headers=h, json={"name": "x"})).status_code == 404
        assert (await c.put(f"/hr/employees/{emp}", headers=h, json={"shift_id": "nope"})).status_code == 404
        r = await c.put(f"/hr/employees/{emp}", headers=h, json={"shift_id": s["id"], "hire_date": "2024-05-01"})
        assert r.status_code == 200
        rows = (await c.get("/hr/employees", headers=h)).json()["items"]
        mine = next(e for e in rows if e["id"] == emp)
        assert (mine["shift_name"], mine["hire_date"]) == ("صباحي", "2024-05-01")
        # A shift in use is stopped, not deleted.
        assert (await c.delete(f"/hr/shifts/{s['id']}", headers=h)).status_code == 204
        shift = next(x for x in (await c.get("/hr/shifts", headers=h)).json() if x["id"] == s["id"])
        assert shift["is_active"] is False and shift["employees"] == 1
        unused = (await c.post("/hr/shifts", headers=h, json={"name": "مسائي", "start_time": "16:00", "end_time": "23:00"})).json()
        assert (await c.delete(f"/hr/shifts/{unused['id']}", headers=h)).status_code == 204
        assert all(x["id"] != unused["id"] for x in (await c.get("/hr/shifts", headers=h)).json())
        # A stopped employee leaves the list, and comes back with include_inactive.
        assert (await c.delete(f"/hr/employees/{emp}", headers=h)).status_code == 204
        assert emp not in {e["id"] for e in (await c.get("/hr/employees", headers=h)).json()["items"]}
        everyone = (await c.get("/hr/employees", params={"include_inactive": "true"}, headers=h)).json()["items"]
        assert next(e for e in everyone if e["id"] == emp)["is_active"] is False
        assert (await c.put(f"/hr/employees/{emp}", headers=h, json={"is_active": True})).status_code == 200


async def test_the_breakdown_shows_how_the_net_was_made():
    from app.activities.general.modules.hr.services import payroll

    ws = await _workspace()
    db, user = await _session(ws)
    async with db:
        await _attend(db, ws["emps"][0], 3)
        await db.commit()
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        entry_id = await _scalar(db, "SELECT id FROM hr_payroll_entries WHERE employee_id = :e", e=ws["emps"][0])
    async with _client() as c:
        r = await c.get(f"/hr/payroll/{entry_id}/breakdown", headers=_headers(ws, "admin"))
    body = r.json()
    assert r.status_code == 200 and body["month"] == MONTH and body["period_status"] == "draft"
    assert body["entry"]["base_pay"] == "100.00" and body["entry"]["advances_carried"] == "0.00"
    assert any(d["date"] == "2025-02-03" and d["status"] == "present" for d in body["breakdown"])


async def test_payslips_name_the_workspaces_currency():
    """Old code: "EGP" was written into every payslip, whatever the workspace's currency."""
    from app.activities.general.modules.hr.routes import hr as routes
    from app.activities.general.modules.hr.services import payroll

    ws = await _workspace()
    db, user = await _session(ws)
    async with db:
        await _attend(db, ws["emps"][0], 3)
        await db.execute(text("INSERT INTO store_settings (key, value) VALUES ('currency', 'SAR') "
                              "ON CONFLICT (tenant_id, key) DO UPDATE SET value = EXCLUDED.value"))
        await db.commit()
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        ticket = (await routes.employee_report(emp_id=ws["emps"][0], month=MONTH, report_type="ticket", db=db, _=user)).body.decode()
        detailed = (await routes.employee_report(emp_id=ws["emps"][0], month=MONTH, report_type="detailed", db=db, _=user)).body.decode()
    assert "ر.س" in ticket and "EGP" not in ticket
    assert "ر.س" in detailed and "EGP" not in detailed
