"""The website's cookieless measurement (ADR-016): a beacon adds one to a daily counter and
stores nothing about the visitor; junk, crawlers and unknown events are dropped silently."""
import json
import os
import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from main import app
from sqlalchemy import text

from app.platform.site_analytics import service

BROWSER = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"


def test_paths_and_hosts_are_cleaned():
    assert service.clean_path("/Pricing/?utm_source=x#plans") == "/pricing"
    assert service.clean_path("/") == "/"
    assert service.clean_path("/en/about") == "/en/about"
    assert service.clean_path("https://evil.example/") is None
    assert service.clean_path("/<script>") is None
    assert service.clean_path("/" + "a" * 300) is None
    assert service.clean_host("WWW.Google.com") == "google.com"
    assert service.clean_host("bad host") == ""
    assert service.is_bot("Mozilla/5.0 (compatible; Googlebot/2.1)")
    assert service.is_bot("Mozilla/5.0 ... Chrome-Lighthouse")
    assert service.is_bot(None)
    assert not service.is_bot(BROWSER)


pytestmark_db = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture
async def client():
    from app.db.base import engine
    from website_api.routers import analytics

    await engine.dispose()
    app.dependency_overrides[analytics.beacon_limiter] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"User-Agent": BROWSER}) as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def counts(path: str) -> list[tuple]:
    from app.db.base import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            text("SELECT kind, name, lang, ref_host, count FROM site_analytics_daily WHERE path = :p AND day = :d "
                 "ORDER BY kind, name, ref_host"), {"p": path, "d": date.today()})
        return [tuple(r) for r in rows]


async def cleanup(path: str) -> None:
    from app.db.base import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM site_analytics_daily WHERE path LIKE :p"), {"p": f"{path}%"})
        await db.commit()


def beacon(**body) -> str:
    return json.dumps(body)


@pytestmark_db
async def test_page_views_and_events_add_up_per_day(client):
    path = f"/test-{uuid.uuid4().hex[:8]}"
    try:
        for _ in range(3):
            r = await client.post("/analytics/event", content=beacon(kind="pageview", name="page_view", path=path, lang="ar"),
                                  headers={"Content-Type": "text/plain"})
            assert r.status_code == 204
            # Cookieless: the answer sets nothing (not even the CSRF cookie every other answer gets).
            assert "set-cookie" not in r.headers
        await client.post("/analytics/event", content=beacon(kind="pageview", name="page_view", path=path + "/?x=1",
                                                             lang="en", ref="www.Google.com"))
        await client.post("/analytics/event", content=beacon(kind="event", name="whatsapp_click", path=path, lang="ar"))
        await client.post("/analytics/event", content=beacon(kind="event", name="demo_request", path=path, lang="ar"))
        assert await counts(path) == [
            ("event", "demo_request", "ar", "", 1),
            ("event", "whatsapp_click", "ar", "", 1),
            ("pageview", "page_view", "ar", "", 3),
            ("pageview", "page_view", "en", "google.com", 1),
        ]
    finally:
        await cleanup(path)


@pytestmark_db
async def test_junk_crawlers_and_unknown_events_are_dropped_without_an_error(client):
    path = f"/test-{uuid.uuid4().hex[:8]}"
    try:
        bad = [
            "not json",
            beacon(kind="pageview", name="page_view", path=path, lang="fr"),
            beacon(kind="event", name="drop_table", path=path, lang="ar"),
            beacon(kind="pageview", name="whatsapp_click", path=path, lang="ar"),
            beacon(kind="pageview", name="page_view", path="https://evil.example/", lang="ar"),
            beacon(kind="pageview", name="page_view", path=path, lang="ar", extra="x" * 3000),
        ]
        for body in bad:
            r = await client.post("/analytics/event", content=body)
            assert r.status_code == 204
        r = await client.post("/analytics/event", content=beacon(kind="pageview", name="page_view", path=path, lang="ar"),
                              headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"})
        assert r.status_code == 204
        assert await counts(path) == []
    finally:
        await cleanup(path)


@pytestmark_db
async def test_nothing_about_the_visitor_is_stored(client):
    from app.db.base import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        cols = (await db.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'site_analytics_daily' ORDER BY 1"
        ))).scalars().all()
    assert cols == ["count", "day", "kind", "lang", "name", "path", "ref_host"]


@pytestmark_db
async def test_the_summary_adds_the_days_up():
    from app.db.base import AsyncSessionLocal, engine

    await engine.dispose()
    path = f"/test-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            for _ in range(2):
                await service.record(db, kind="pageview", name="page_view", path=path, lang="ar", ref_host="facebook.com")
            await service.record(db, kind="event", name="signup_start", path=path, lang="ar")
            s = await service.summary(db, days=7)
        assert {"path": path, "views": 2} in s["pages"]
        assert any(r["host"] == "facebook.com" and r["views"] >= 2 for r in s["referrers"])
        assert any(e["name"] == "signup_start" for e in s["events"])
        assert s["page_views"] >= 2 and s["by_day"][-1]["day"] == date.today().isoformat()
    finally:
        await cleanup(path)
        await engine.dispose()
