"""The workspace's clock (PLAT-8): what moment, day and month it is where the workspace works.

Every workspace works in Africa/Cairo for now: there is no time zone setting yet, and when one comes
it is read here and nowhere else. Day boundaries (reports, the daily ledger), the current month
(closing periods, `require_open_period`, payroll), posting dates of the ledger and dates written on
documents all come from here, never from the server's clock: the servers run in UTC, so a sale at
00:30 in Cairo belonged to the day before.

SQL that groups timestamps by day uses `AT TIME ZONE '<TZ_NAME>'` with the same name.

Tests freeze time by replacing `now` (every helper here reads it).
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ_NAME = "Africa/Cairo"
TZ = ZoneInfo(TZ_NAME)
_UTC = ZoneInfo("UTC")


def now() -> datetime:
    """This moment in the workspace's time zone (aware)."""
    return datetime.now(TZ)


def today() -> date:
    return now().date()


def current_month() -> str:
    """The workspace's current month, "YYYY-MM"."""
    return now().strftime("%Y-%m")


def local_date(moment: datetime | date | None) -> date:
    """The workspace's date of a moment (naive datetimes are UTC, as the database returns them)."""
    if moment is None:
        return today()
    if isinstance(moment, datetime):
        return (moment if moment.tzinfo else moment.replace(tzinfo=_UTC)).astimezone(TZ).date()
    return moment


def day_start(d: date) -> datetime:
    """The first moment of a day in the workspace's time zone."""
    return datetime.combine(d, time.min, tzinfo=TZ)


def day_bounds(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    """[start, end) covering the days from `date_from` to `date_to` included (either may be None)."""
    start = day_start(date_from) if date_from else None
    end = day_start(date_to + timedelta(days=1)) if date_to else None
    return start, end


def stamp(fmt: str = "%Y/%m/%d  %H:%M") -> str:
    """This moment as text, for "printed at" lines on documents."""
    return now().strftime(fmt)
