"""hr module: settings, employees, shifts, attendance, advances, import-csv,
payroll flow (calculate -> submit -> approve -> pay),
breakdown, monthly report, employee report."""
from datetime import datetime

from helpers import uid

from conftest import (admin_api, owner_api, reg, db)  # noqa: F401


def _now_month() -> str:
    return datetime.now().strftime("%Y-%m")


def _future_month() -> str:
    now = datetime.now()
    return f"{now.year + 1}-{now.month:02d}"


def _emp_payload(name: str):
    return {
        "emp_code": "E2E-" + uid("e", 6).upper(),
        "name": name,
        "position": "اختبار",
        "monthly_salary": "5000",
        "hire_date": "2024-01-01",
        "is_active": True,
    }


def _employee(owner_api, reg):
    name = "E2E-EMP-" + uid("e")
    e = owner_api.ok(owner_api.post("/hr/employees", json=_emp_payload(name)))
    reg.add("employee", e["id"])
    return e


def test_hr_settings(owner_api):
    body = owner_api.ok(owner_api.get("/hr/settings"))
    put = owner_api.put("/hr/settings", json={"late_threshold_minutes": 5})
    if put.status_code in (200, 201):
        owner_api.ok(put)
    assert body is not None


def test_hr_shifts_crud(owner_api, reg):
    name = "E2E-HRSHIFT-" + uid("h")
    s = owner_api.ok(owner_api.post("/hr/shifts", json={
        "name": name, "start_time": "09:00", "end_time": "17:00"}))
    reg.add("employee_shift", s["id"])
    shifts = owner_api.ok(owner_api.get("/hr/shifts"))
    assert any(x["id"] == s["id"] for x in shifts)


def test_hr_employees_crud_and_attendance(owner_api, reg):
    e = _employee(owner_api, reg)
    lst = owner_api.ok(owner_api.get("/hr/employees"))
    assert any(x["id"] == e["id"] for x in lst)

    upd = owner_api.ok(owner_api.put(f"/hr/employees/{e['id']}",
                                     json={"position": "مدير اختبار"}))
    assert upd.get("position") == "مدير اختبار" or upd.get("detail") == "updated"

    att = owner_api.ok(owner_api.post("/hr/attendance", json={
        "employee_id": e["id"],
        "work_date": datetime.now().strftime("%Y-%m-%d"),
        "check_in": "09:00",
        "check_out": "17:00",
    }))
    reg.add("attendance", att.get("id") or "")

    rows = owner_api.ok(owner_api.get("/hr/attendance", params={"employee_id": e["id"]}))
    assert any(x.get("employee_id") == e["id"] for x in rows)

    for rep in ("/hr/attendance/report", "/hr/payroll/report/monthly"):
        r = owner_api.get(rep, params={"month": _now_month(), "token": _print_token(owner_api)})
        assert r.status_code == 200, rep


def test_hr_advances(owner_api, reg):
    e = _employee(owner_api, reg)
    adv = owner_api.ok(owner_api.post("/hr/advances", json={
        "employee_id": e["id"], "amount": "200",
        "date": datetime.now().strftime("%Y-%m-%d"), "notes": "e2e"}))
    reg.add("advance", adv.get("id") or "")
    rows = owner_api.ok(owner_api.get("/hr/advances", params={"employee_id": e["id"]}))
    assert isinstance(rows, list)


def test_hr_import_csv_and_no_device_sync(owner_api):
    r = owner_api.post("/hr/attendance/import-csv", json=None)
    assert r.status_code in (200, 400, 422), r.text[:200]
    # Device attendance sync was removed (#110): attendance comes from entry and CSV import.
    for method, path in (("post", "/hr/attendance/from-device"), ("post", "/hr/sync-device"), ("get", "/hr/sync-log"),
                         ("get", "/modules/zk_attendance/devices")):
        assert getattr(owner_api, method)(path).status_code in (404, 405), path


def test_payroll_full_flow(owner_api, reg):
    e = _employee(owner_api, reg)
    month = _future_month()

    calc = owner_api.ok(owner_api.post("/hr/payroll/calculate", json={"month": month}))
    assert calc["month"] == month

    rows = owner_api.ok(owner_api.get("/hr/payroll", params={"month": month}))
    mine = [p for p in rows if p.get("employee_id") == e["id"]]
    assert len(mine) >= 1, rows

    breakd = owner_api.ok(owner_api.get(f"/hr/payroll/{mine[0]['id']}/breakdown"))
    assert "breakdown" in breakd or "employee" in breakd

    adj = owner_api.ok(owner_api.put(f"/hr/payroll/{mine[0]['id']}",
                                     json={"bonus": "100"}))
    assert adj is not None

    period = owner_api.ok(owner_api.get("/hr/payroll/period", params={"month": month}))
    reg.add("hr_period", period["id"])

    if period.get("status") == "draft":
        sub = owner_api.ok(owner_api.post("/hr/payroll/period/submit", params={"month": month}))
        assert sub["detail"] == "submitted"
        appr = owner_api.ok(owner_api.post("/hr/payroll/period/approve", params={"month": month}))
        assert appr["detail"] == "approved"
        exps = owner_api.ok(owner_api.get("/expenses", params={"search": "رواتب"}))
        for x in (exps if isinstance(exps, list) else exps.get("data", [])):
            if x.get("notes") == f"HR payroll month {month}":
                reg.add("expense", x["id"])
        pay = owner_api.ok(owner_api.post("/hr/payroll/period/pay", params={"month": month}))
        assert pay["detail"] == "paid"
        # paid month cannot be reopened
        r = owner_api.post("/hr/payroll/period/reopen", params={"month": month})
        assert r.status_code in (400, 409), r.text[:200]
    else:
        r = owner_api.post("/hr/payroll/period/reopen", params={"month": month})
        assert r.status_code in (200, 400, 409), r.text[:200]


def _print_token(api) -> str:
    """Reports open in a browser tab with a short-lived print token, as the app does."""
    return api.ok(api.post("/auth/print-token", json={}))["token"]


def test_payroll_reports(owner_api, reg):
    e = _employee(owner_api, reg)
    r = owner_api.get(f"/hr/payroll/report/employee/{e['id']}", params={"month": _now_month(), "token": _print_token(owner_api)})
    assert r.status_code == 200

def test_salary_change_is_audited_and_unknown_employee_is_404(owner_api, reg, db):
    e = _employee(owner_api, reg)
    owner_api.ok(owner_api.put(f"/hr/employees/{e['id']}", json={"monthly_salary": "7777"}))
    assert db.one("SELECT count(*) FROM hr_audit_log WHERE entity_id = %s AND reason = 'تعديل الراتب'", (e["id"],))[0] == 1

    ghost = "00000000-0000-0000-0000-000000000000"
    assert owner_api.put(f"/hr/employees/{ghost}", json={"position": "x"}).status_code == 404
    r = owner_api.post("/hr/attendance", json={"employee_id": ghost, "work_date": datetime.now().strftime("%Y-%m-%d")})
    assert r.status_code == 404, r.text[:200]


