"""Counting the website's page views and events, and reading the totals (ADR-016).

The website sends a beacon per page view or event (website API, POST /analytics/event); this
adds one to the day's counter. The Mizan team reads the totals in the admin panel."""
from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import SiteAnalyticsDaily as Row

EVENTS = frozenset({"whatsapp_click", "phone_click", "contact_submit", "demo_request", "signup_start", "signup_complete"})
_PATH = re.compile(r"^/[a-z0-9/_.\-]{0,159}$")
_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.\-]{0,98}[a-z0-9])?$")
_BOT = re.compile(r"bot|crawl|spider|slurp|lighthouse|headless|preview|fetch|monitor|python|curl|wget", re.I)


def is_bot(user_agent: str | None) -> bool:
    """Crawlers and test browsers aren't visitors (the user agent is read here, never stored)."""
    return not user_agent or bool(_BOT.search(user_agent))


def clean_path(raw: str) -> str | None:
    """The page's path only: no query, no fragment, lower case, no trailing slash; None if odd."""
    path = raw.split("?", 1)[0].split("#", 1)[0].lower()
    if len(path) > 1:
        path = path.rstrip("/")
    return path if _PATH.match(path) else None


def clean_host(raw: str | None) -> str:
    host = (raw or "").strip().lower().removeprefix("www.")
    return host if _HOST.match(host) else ""


async def record(db: AsyncSession, *, kind: str, name: str, path: str, lang: str, ref_host: str = "",
                 day: date | None = None) -> None:
    stmt = insert(Row).values(day=day or date.today(), kind=kind, name=name, path=path, lang=lang,
                              ref_host=ref_host, count=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Row.day, Row.kind, Row.name, Row.path, Row.lang, Row.ref_host],
        set_={"count": Row.count + 1},
    )
    await db.execute(stmt)
    await db.commit()


async def summary(db: AsyncSession, days: int = 30) -> dict:
    """Totals over the last `days` days (today included)."""
    since = date.today() - timedelta(days=days - 1)
    recent = Row.day >= since
    views = (Row.kind == "pageview") & recent

    async def rows(*cols, where, group, order, limit=None):
        q = select(*cols, func.sum(Row.count).label("n")).where(where).group_by(*group).order_by(*order)
        return (await db.execute(q.limit(limit) if limit else q)).all()

    by_day = await rows(Row.day, where=views, group=[Row.day], order=[Row.day])
    pages = await rows(Row.path, where=views, group=[Row.path], order=[func.sum(Row.count).desc(), Row.path], limit=50)
    langs = await rows(Row.lang, where=views, group=[Row.lang], order=[Row.lang])
    refs = await rows(Row.ref_host, where=views & (Row.ref_host != ""), group=[Row.ref_host],
                      order=[func.sum(Row.count).desc(), Row.ref_host], limit=20)
    events = await rows(Row.name, where=(Row.kind == "event") & recent, group=[Row.name],
                        order=[func.sum(Row.count).desc(), Row.name])
    event_pages = await rows(Row.name, Row.path, where=(Row.kind == "event") & recent, group=[Row.name, Row.path],
                             order=[func.sum(Row.count).desc(), Row.name, Row.path], limit=50)
    return {
        "since": since.isoformat(),
        "days": days,
        "page_views": sum(int(r.n) for r in by_day),
        "by_day": [{"day": r.day.isoformat(), "views": int(r.n)} for r in by_day],
        "pages": [{"path": r.path, "views": int(r.n)} for r in pages],
        "languages": [{"lang": r.lang, "views": int(r.n)} for r in langs],
        "referrers": [{"host": r.ref_host, "views": int(r.n)} for r in refs],
        "events": [{"name": r.name, "count": int(r.n)} for r in events],
        "event_pages": [{"name": r.name, "path": r.path, "count": int(r.n)} for r in event_pages],
    }
