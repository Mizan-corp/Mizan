"""HR made production ready (PRODUCTION_READINESS.md, `hr`): payroll entries are frozen once the
month is approved, paying pays exactly what was approved, salaries are readable only with
`payroll`, reports of approved months come from the stored entries, attendance and HR records of
closed months can't change, advances can be cancelled, the models match the schema, and report
HTML escapes what users typed."""
import asyncio
import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from app.platform.tenancy.models import Tenant

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

D = Decimal
MONTH = "2025-02"  # a past month: the engine walks all of it
MODULES = ["sales", "pos", "shifts", "inventory", "finance", "contacts", "purchases", "hr", "accounting"]


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _workspace() -> dict:
    """A workspace with accounting, an admin, a cashier, an accountant, a safe holding 10000 and two
    employees (salary 2600 each)."""
    from app.models.registry import load_all_models
    from app.platform.permissions.access import set_access
    from app.platform.permissions.roles import standard_permissions
    from app.platform.tenancy.context import install_tenancy_events

    load_all_models()
    install_tenancy_events()
    tid = uuid.uuid4()
    current_tenant_id.set(None)
    users = {}
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=tid, name=f"HR {tid.hex[:6]}", slug=f"hr-{tid.hex[:8]}", status="active", active_modules=MODULES))
        await s.flush()
        for role in ("admin", "cashier", "accountant"):
            u = User(id=uuid.uuid4(), tenant_id=tid, username=f"hr{role[:3]}_{tid.hex[:8]}", full_name=role, role=role,
                     password_hash=hash_password("Pass12345!"), permissions=standard_permissions(role), is_active=True)
            s.add(u)
            users[role] = u
        await s.flush()
        await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        for role, u in users.items():  # the standard role (give_roles would also touch other tests' users)
            await set_access(s, u, role)
        users = {role: u.id for role, u in users.items()}
        await s.commit()
    current_tenant_id.set(tid)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, tid)
        safe_id = uuid.uuid4()
        await s.execute(text("INSERT INTO safes (id, tenant_id, name, balance) VALUES (:id, :t, 'الخزينة الرئيسية', 10000)"),
                        {"id": safe_id, "t": tid})
        emps = []
        for name in ("موظف أ", "موظف ب"):
            emps.append((await s.execute(text("""
                INSERT INTO hr_employees (id, tenant_id, emp_code, name, monthly_salary, shift_schedule)
                VALUES (:id, :t, :code, :n, 2600, '09:00-17:00') RETURNING id
            """), {"id": uuid.uuid4(), "t": tid, "code": f"E{len(emps)}-{tid.hex[:4]}", "n": name})).scalar_one())
        await s.commit()
    return {"tid": tid, "users": users, "safe_id": safe_id, "emps": emps}


async def _session(ws, role: str = "admin"):
    db = AsyncSessionLocal()
    await bind_tenant(db, ws["tid"])
    user = await db.get(User, ws["users"][role])
    db.expunge(user)
    return db, user


def _headers(ws, role: str) -> dict:
    token = create_access_token({"sub": str(ws["users"][role]), "role": role, "username": role, "tid": str(ws["tid"])})
    return {"Authorization": f"Bearer {token}"}


def _client() -> AsyncClient:
    from main import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _attend(db, emp, day: int, ci=9, co=17):
    d = date(int(MONTH[:4]), int(MONTH[5:]), day)
    await db.execute(text("""
        INSERT INTO hr_attendance (id, tenant_id, employee_id, work_date, check_in, check_out, status)
        VALUES (:id, :t, :e, :d, :ci, :co, 'present')
    """), {"id": uuid.uuid4(), "t": current_tenant_id.get(), "e": emp, "d": d,
           "ci": datetime(d.year, d.month, d.day, ci, tzinfo=UTC), "co": datetime(d.year, d.month, d.day, co, tzinfo=UTC)})


async def _scalar(db, sql: str, **params):
    return (await db.execute(text(sql), params)).scalar()


# ── HR-1 / HR-10: entries frozen after approval; pay exactly the approved amount ──────────────

async def test_entry_edits_keep_the_proration_and_stop_at_approval():
    """Old code: the edit rebuilt the net from the full base salary (2600 + 100), let `status` be
    set by hand, and kept accepting edits after approval."""
    from app.activities.general.modules.hr.routes import hr as routes
    from app.activities.general.modules.hr.schemas import PayrollUpdate
    from app.activities.general.modules.hr.services import payroll

    ws = await _workspace()
    db, user = await _session(ws)
    async with db:
        for day in (2, 3, 4, 5):  # four days of 8 hours out of 26 × 8
            await _attend(db, ws["emps"][0], day)
        await db.commit()
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        entry = (await db.execute(text("SELECT id, net_salary, base_pay FROM hr_payroll_entries WHERE employee_id=:e"),
                                  {"e": ws["emps"][0]})).one()
        assert entry.base_pay == D("400.00") and entry.net_salary == D("400.00")  # 2600 × 32 / 208

        r = await routes.update_payroll(entry.id, PayrollUpdate(bonus=D("100")), db=db, current_user=user)
        assert r["net_salary"] == 500.0
        with pytest.raises(ValidationError):
            PayrollUpdate(bonus=D("1"), status="paid")

        await payroll.submit_payroll_period(db, MONTH, str(user.id))
        await payroll.approve_payroll_period(db, MONTH, str(user.id))
        with pytest.raises(HTTPException) as e:
            await routes.update_payroll(entry.id, PayrollUpdate(bonus=D("900")), db=db, current_user=user)
        assert e.value.status_code == 409 and "معتمدة" in e.value.detail
        await db.rollback()
        assert await _scalar(db, "SELECT net_salary FROM hr_payroll_entries WHERE id=:i", i=entry.id) == D("500.00")


async def test_paying_pays_the_approved_total_and_keeps_the_expense():
    """Old code: paying summed the entries again (whatever they had become) and rewrote the
    approved expense's amount with it."""
    from app.activities.general.modules.hr.services import payroll

    ws = await _workspace()
    db, user = await _session(ws)
    async with db:
        await _attend(db, ws["emps"][0], 2)
        await db.commit()
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        await payroll.submit_payroll_period(db, MONTH, str(user.id))
        approved = await payroll.approve_payroll_period(db, MONTH, str(user.id))
        assert approved == 100.0
        period = (await db.execute(text("SELECT id, expense_id, approved_amount FROM hr_payroll_periods WHERE month=:m"),
                                   {"m": MONTH})).one()
        assert period.approved_amount == D("100.00")

        # The entries changed behind the approval: paying refuses, nothing moves.
        await db.execute(text("UPDATE hr_payroll_entries SET net_salary = net_salary + 900 WHERE period_id=:p"),
                         {"p": period.id})
        await db.commit()
        with pytest.raises(HTTPException) as e:
            await payroll.pay_payroll_period(db, MONTH, str(user.id), safe_id=ws["safe_id"])
        assert e.value.status_code == 409
        await db.rollback()
        assert await _scalar(db, "SELECT balance FROM safes WHERE id=:s", s=ws["safe_id"]) == D("10000.00")

        await db.execute(text("UPDATE hr_payroll_entries SET net_salary = net_salary - 900 WHERE period_id=:p"),
                         {"p": period.id})
        await db.commit()
        assert await payroll.pay_payroll_period(db, MONTH, str(user.id), safe_id=ws["safe_id"]) == 100.0
        assert await _scalar(db, "SELECT balance FROM safes WHERE id=:s", s=ws["safe_id"]) == D("9900.00")
        assert await _scalar(db, "SELECT amount FROM expenses WHERE id=:i", i=period.expense_id) == D("100.00")
        assert await _scalar(db, "SELECT paid_amount FROM hr_payroll_periods WHERE id=:p", p=period.id) == D("100.00")


async def test_calculation_waits_for_an_approval_in_progress():
    """Old code: calculate read the status without a lock, so it rewrote the entries while another
    transaction was approving them."""
    from app.activities.general.modules.hr.services import payroll

    ws = await _workspace()
    db, user = await _session(ws)
    async with db:
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        await payroll.submit_payroll_period(db, MONTH, str(user.id))
    approver, _ = await _session(ws)
    calculator, _ = await _session(ws)
    async with approver, calculator:
        await approver.execute(text("SELECT id FROM hr_payroll_periods WHERE month=:m FOR UPDATE"), {"m": MONTH})
        await approver.execute(text("UPDATE hr_payroll_periods SET status='approved' WHERE month=:m"), {"m": MONTH})
        calc = asyncio.create_task(payroll.calculate_payroll_month(calculator, MONTH, str(user.id)))
        await asyncio.sleep(1.0)
        assert not calc.done(), "the calculation ran while the month was being approved"
        await approver.commit()
        with pytest.raises(HTTPException, match="اعتماد"):
            await calc


# ── HR-2: pay is readable only with the payroll permission ────────────────────────────────

READS = ["/hr/employees", "/hr/payroll", f"/hr/payroll?month={MONTH}", "/hr/attendance", "/hr/advances",
         "/hr/shifts", "/hr/settings", "/hr/audit-log", f"/hr/payroll/period?month={MONTH}"]


async def test_a_cashier_reads_no_salaries():
    ws = await _workspace()
    db, user = await _session(ws)
    async with db:
        from app.activities.general.modules.hr.services import payroll
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        entry_id = await _scalar(db, "SELECT id FROM hr_payroll_entries LIMIT 1")
    async with _client() as c:
        for path in READS + [f"/hr/payroll/{entry_id}/breakdown"]:
            r = await c.get(path, headers=_headers(ws, "cashier"))
            assert r.status_code == 403, (path, r.status_code)
            r = await c.get(path, headers=_headers(ws, "admin"))
            assert r.status_code == 200, (path, r.status_code, r.text[:200])
        # Accountants keep payroll; they pay but don't approve (payroll:approve).
        assert (await c.get("/hr/employees", headers=_headers(ws, "accountant"))).status_code == 200
        r = await c.post(f"/hr/payroll/period/approve?month={MONTH}", headers=_headers(ws, "accountant"))
        assert r.status_code == 403
        # Print tokens: a cashier's can't open the payroll reports.
        cashier_print = create_access_token({"sub": str(ws["users"]["cashier"]), "tid": str(ws["tid"]), "scope": "print"})
        for path in (f"/hr/payroll/report/monthly?month={MONTH}", f"/hr/attendance/report?month={MONTH}",
                     f"/hr/payroll/report/employee/{ws['emps'][0]}?month={MONTH}"):
            assert (await c.get(path + f"&token={cashier_print}")).status_code == 403, path


async def test_journal_writers_without_payroll_see_names_not_pay():
    from app.activities.general.modules.hr.routes import hr as routes

    ws = await _workspace()
    db, _ = await _session(ws)
    async with db:
        clerk = User(id=uuid.uuid4(), tenant_id=ws["tid"], username="clerk", full_name="كاتب",
                     password_hash="x", is_active=True)
        clerk.effective_permissions = frozenset({"accounting:view", "accounting:journal"})
        rows = (await routes.list_employees(db=db, current_user=clerk))["items"]
    assert {r["name"] for r in rows} == {"موظف أ", "موظف ب"}
    assert all("monthly_salary" not in r for r in rows)


# ── HR-3: reports of an approved month come from the stored entries ──────────────────────

async def test_payslips_of_an_approved_month_show_what_was_approved():
    """Old code: the payslip and the monthly report recomputed from today's salary and attendance."""
    from app.activities.general.modules.hr.routes import hr as routes
    from app.activities.general.modules.hr.services import payroll

    ws = await _workspace()
    db, user = await _session(ws)
    async with db:
        for day in (2, 3):
            await _attend(db, ws["emps"][0], day)
        await db.commit()
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        await db.execute(text("""
            UPDATE hr_payroll_entries SET daily_breakdown = CAST(:b AS jsonb) WHERE employee_id=:e
        """), {"e": ws["emps"][0], "b": '[{"date": "2025-02-02", "status": "present", "work_hours": 8, '
                                         '"late_minutes": 0, "overtime_hours": 0, "note": "يوم محفوظ"}]'})
        await db.commit()
        await payroll.submit_payroll_period(db, MONTH, str(user.id))
        await payroll.approve_payroll_period(db, MONTH, str(user.id))
        # Afterwards the salary changes (allowed): the approved month's papers don't.
        await db.execute(text("UPDATE hr_employees SET monthly_salary = 52000 WHERE id=:e"), {"e": ws["emps"][0]})
        await db.commit()

        ticket = (await routes.employee_report(emp_id=ws["emps"][0], month=MONTH, report_type="ticket", db=db, _=user)).body.decode()
        assert "200.00" in ticket and "4,000.00" not in ticket
        detailed = (await routes.employee_report(emp_id=ws["emps"][0], month=MONTH, report_type="detailed", db=db, _=user)).body.decode()
        assert "يوم محفوظ" in detailed
        monthly = (await routes.payroll_monthly_report(month=MONTH, db=db, _=user)).body.decode()
        assert "200.00" in monthly and "4,000.00" not in monthly


# ── HR-4: attendance of closed months; manual days survive a CSV import ──────────────────

async def test_attendance_is_closed_with_the_month_and_manual_days_survive_imports():
    from app.activities.general.modules.hr.routes import hr as routes
    from app.activities.general.modules.hr.schemas import AttendanceCreate
    from app.activities.general.modules.hr.services import attendance, payroll

    ws = await _workspace()
    emp = ws["emps"][0]
    code = (f"E0-{ws['tid'].hex[:4]}")
    db, user = await _session(ws)
    async with db:
        await routes.add_attendance(AttendanceCreate(employee_id=emp, work_date=date(2025, 2, 3), check_in="10:00",
                                                     check_out="18:00", edit_reason="نسي البصمة"),
                                    db=db, current_user=user)
        row = (await db.execute(text("SELECT edited, edited_by, edit_reason FROM hr_attendance WHERE employee_id=:e"),
                                {"e": emp})).one()
        assert row.edited is True and row.edited_by == str(user.id) and row.edit_reason == "نسي البصمة"

        csv = f"Employee Code,Date,Check In,Check Out\n{code},2025-02-03,08:00,12:00\n{code},2025-02-04,09:00,17:00\n"
        out = await attendance.import_attendance_csv_stream(db, csv.encode())
        assert out["added"] == 1 and out["updated"] == 0 and out["skipped"] == 1
        kept = await _scalar(db, "SELECT check_in FROM hr_attendance WHERE employee_id=:e AND work_date='2025-02-03'", e=emp)
        assert kept.hour == 10

        with pytest.raises(HTTPException) as e:
            await attendance.import_attendance_csv_stream(db, b"\xff\xfe\x00bad")
        assert e.value.status_code == 400

        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        await payroll.submit_payroll_period(db, MONTH, str(user.id))
        await payroll.approve_payroll_period(db, MONTH, str(user.id))
        with pytest.raises(HTTPException) as e:
            await routes.add_attendance(AttendanceCreate(employee_id=emp, work_date=date(2025, 2, 10), check_in="09:00"),
                                        db=db, current_user=user)
        assert e.value.status_code == 409
        await db.rollback()
        out = await attendance.import_attendance_csv_stream(db, f"Employee Code,Date,Check In\n{code},2025-02-11,09:00\n".encode())
        assert out["added"] == 0 and out["skipped"] == 1 and "2025-02" in out["errors"][0]
        assert await _scalar(db, "SELECT count(*) FROM hr_attendance WHERE employee_id=:e", e=emp) == 2


# ── HR-8: advances ───────────────────────────────────────────────────────────────────────

async def test_advances_check_the_employee_and_the_month_and_can_be_cancelled():
    from app.activities.general.modules.hr.routes import hr as routes
    from app.activities.general.modules.hr.schemas import AdvanceCreate
    from app.activities.general.modules.hr.services import payroll

    ws, other = await _workspace(), await _workspace()
    current_tenant_id.set(ws["tid"])
    db, user = await _session(ws)
    async with db:
        # Another workspace's employee: refused before any cash moves (the foreign key let it in).
        with pytest.raises(HTTPException) as e:
            await routes.add_advance(AdvanceCreate(employee_id=other["emps"][0], amount=D("300"), date=date(2025, 2, 5),
                                                   safe_id=ws["safe_id"]), db=db, current_user=user)
        assert e.value.status_code == 404
        await db.rollback()
        assert await _scalar(db, "SELECT balance FROM safes WHERE id=:s", s=ws["safe_id"]) == D("10000.00")
        with pytest.raises(ValidationError):
            AdvanceCreate(employee_id=ws["emps"][0], amount=D("1"), record_type="هدية")

        adv = await routes.add_advance(AdvanceCreate(employee_id=ws["emps"][0], amount=D("300"), date=date(2025, 2, 5),
                                                     safe_id=ws["safe_id"]), db=db, current_user=user)
        assert await _scalar(db, "SELECT balance FROM safes WHERE id=:s", s=ws["safe_id"]) == D("9700.00")
        assert await _scalar(db, "SELECT count(*) FROM acc_entries WHERE source_type='hr_advance' AND source_id=:i",
                             i=uuid.UUID(adv["id"])) == 1

        cancelled = await routes.cancel_advance(uuid.UUID(adv["id"]), None, db=db, current_user=user)
        assert cancelled["status"] == "cancelled"
        assert await _scalar(db, "SELECT balance FROM safes WHERE id=:s", s=ws["safe_id"]) == D("10000.00")
        assert await _scalar(db, "SELECT count(*) FROM acc_entries WHERE source_type='hr_advance' AND source_id=:i "
                                 "AND event='reverse'", i=uuid.UUID(adv["id"])) == 1
        assert (await payroll.load_hr_records_for_month(db, ws["emps"][0], MONTH))["advance"] == 0
        with pytest.raises(HTTPException) as e:
            await routes.cancel_advance(uuid.UUID(adv["id"]), None, db=db, current_user=user)
        assert e.value.status_code == 409
        await db.rollback()

        # A closed month takes no new records and keeps its old ones.
        bonus = await routes.add_advance(AdvanceCreate(employee_id=ws["emps"][0], amount=D("50"), date=date(2025, 2, 6),
                                                       record_type="مكافأة"), db=db, current_user=user)
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        await payroll.submit_payroll_period(db, MONTH, str(user.id))
        await payroll.approve_payroll_period(db, MONTH, str(user.id))
        with pytest.raises(HTTPException) as e:
            await routes.add_advance(AdvanceCreate(employee_id=ws["emps"][0], amount=D("20"), date=date(2025, 2, 7),
                                                   record_type="خصم"), db=db, current_user=user)
        assert e.value.status_code == 409
        await db.rollback()
        with pytest.raises(HTTPException) as e:
            await routes.cancel_advance(uuid.UUID(bonus["id"]), None, db=db, current_user=user)
        assert e.value.status_code == 409
        await db.rollback()


# ── HR-6 / HR-7: validation ─────────────────────────────────────────────────────────────

async def test_bad_input_is_refused_not_a_500():
    ws = await _workspace()
    h = _headers(ws, "admin")
    async with _client() as c:
        for path in ("/hr/payroll/period?month=2025-13", "/hr/payroll/period?month=x'; --",
                     "/hr/attendance?employee_id=nope", "/hr/advances?employee_id=1"):
            assert (await c.get(path, headers=h)).status_code == 422, path
        assert (await c.post("/hr/payroll/calculate", headers=h, json={"month": "2025-2"})).status_code == 422
        # GET period reads only: no period row appears.
        r = await c.get("/hr/payroll/period?month=2031-01", headers=h)
        assert r.status_code == 200 and r.json() == {"id": None, "month": "2031-01", "status": "draft"}
        r = await c.post("/hr/employees", headers=h, json={"name": "مكرر", "emp_code": f"E0-{ws['tid'].hex[:4]}"})
        assert r.status_code == 409, r.text
        assert (await c.post("/hr/employees", headers=h, json={"name": "x" * 200})).status_code == 422
        assert (await c.post("/hr/shifts", headers=h, json={"name": "s", "start_time": "25:00", "end_time": "x"})).status_code == 422
        assert (await c.put("/hr/settings", headers=h, json={"settings": {"days_in_month": "x"}})).status_code == 422
        assert (await c.put("/hr/settings", headers=h, json={"settings": {"days_in_month": 30, "weekend_paid": False}})).status_code == 200
        got = (await c.get("/hr/settings", headers=h)).json()  # typed, with the defaults (HR-12)
        assert (got["days_in_month"], got["weekend_paid"], got["weekend_day"], got["paid_leave_days"]) == (30, False, 4, 4)
    db, _ = await _session(ws)
    async with db:
        assert await _scalar(db, "SELECT count(*) FROM hr_payroll_periods WHERE month='2031-01'") == 0
