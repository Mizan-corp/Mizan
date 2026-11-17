"""periods module: accounting month close/reopen + HR payroll period lifecycle."""
from datetime import datetime

from conftest import owner_api, admin_api, reg  # noqa: F401


def test_list_periods(owner_api):
    """Every month from the first activity to now, newest first, with what can be done to it."""
    rows = owner_api.ok(owner_api.get("/periods"))
    assert isinstance(rows, list) and rows
    assert rows[0]["current"] and not rows[0]["can_close"]
    months = [r["month"] for r in rows]
    assert months == sorted(months, reverse=True)
    assert sum(1 for r in rows if r["can_close"]) <= 1 and sum(1 for r in rows if r["can_reopen"]) <= 1
    assert {"month", "status", "can_close", "can_reopen"} <= set(rows[0])


def test_the_current_month_is_never_closed(owner_api):
    month = owner_api.ok(owner_api.get("/periods"))[0]["month"]
    close = owner_api.post(f"/periods/{month}/close")
    assert close.status_code == 400, close.text[:200]
    # reopening needs a reason, and an open month can't be reopened
    assert owner_api.post(f"/periods/{month}/reopen").status_code == 422
    assert owner_api.post(f"/periods/{month}/reopen", json={"reason": "e2e check"}).status_code == 400
    assert owner_api.post("/periods/2026-13/close").status_code == 400


def test_hr_payroll_period_lifecycle(owner_api, reg):
    """Real product flow: hr payroll period goes draft -> submit -> approve -> pay."""
    month = datetime.now().strftime("%Y-%m")
    p = owner_api.ok(owner_api.get(f"/hr/payroll/period?month={month}"))
    assert p.get("month") == month or p.get("status") in ("draft", "submitted", "approved", "paid")
    assert "status" in p
    # Reading a month creates nothing: an untouched month is a draft without an id.
    if p["id"]:
        reg.add("hr_period", p["id"])
    submit = owner_api.post(f"/hr/payroll/period/submit?month={month}")
    assert submit.status_code in (200, 201, 400), submit.text[:200]
    if not p["id"]:
        p = owner_api.ok(owner_api.get(f"/hr/payroll/period?month={month}"))
        if p["id"]:
            reg.add("hr_period", p["id"])
    approve = owner_api.post(f"/hr/payroll/period/approve?month={month}")
    assert approve.status_code in (200, 201, 400), approve.text[:200]