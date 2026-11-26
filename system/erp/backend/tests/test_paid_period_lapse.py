"""A workspace becomes read-only the moment its trial or paid period ends (#66)."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.platform.billing.services.plan_gating import lapse

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def ws(plan, trial=None, paid=None):
    return SimpleNamespace(plan=plan, trial_ends_at=trial, paid_until=paid)


def test_trial_ends():
    assert lapse(ws("trial", trial=NOW + timedelta(seconds=1)), NOW) is None
    assert lapse(ws("trial", trial=NOW - timedelta(seconds=1)), NOW) == "trial"
    assert lapse(ws("trial"), NOW) is None


def test_paid_period_ends_with_no_grace():
    assert lapse(ws("pro", paid=NOW + timedelta(seconds=1)), NOW) is None
    assert lapse(ws("pro", paid=NOW - timedelta(seconds=1)), NOW) == "paid"
    assert lapse(ws("pro", paid=(NOW - timedelta(days=1)).replace(tzinfo=None)), NOW) == "paid"  # naive dates


def test_paid_plan_without_an_end_date_stays_writable():
    assert lapse(ws("enterprise"), NOW) is None
