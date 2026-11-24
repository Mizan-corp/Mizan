"""UI-driven public activation (synthetic scope): service.set_public_access /
get_public_access behind the site.manage-gated pages routes.

The scoped flow can only flip rows on the deployment's own configured host
(PUBLIC_SITE_HOST from server config), the fixed synthetic test-site slug, and
allow_connected_data=False. Connected-data exposure can never be created here.
DB is mocked; service.get_page is patched (its own lookup is covered elsewhere)
so no ORM mapper compilation is needed. Statement parameter values are asserted.
"""
import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY', 'offline-test-not-used-for-signing')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from app.core.config import settings
from app.platform.site import service

TID = uuid.UUID("a1b975ac-32ac-4813-9b35-e43069616c5f")
UID = uuid.UUID("c3c975ac-32ac-4813-9b35-e43069616c5f")
PAGE_ID = uuid.UUID("d4d975ac-32ac-4813-9b35-e43069616c5f")
HOST = "mizan-studio-feature-test.vercel.app"


def page(slug="hello", status="published", published=True):
    p = MagicMock()
    p.slug = slug
    p.status = status
    p.published_tree = {"type": "section", "children": []} if published else None
    return p


def db_with(activation_enabled=None):
    db = AsyncMock()
    row = (MagicMock(enabled=activation_enabled) if activation_enabled is not None else None)
    calls = []

    async def _exec(stmt, params=None):
        calls.append((str(stmt), params))
        r = MagicMock()
        r.first.return_value = row
        return r

    db.execute.side_effect = _exec
    db._calls = calls
    return db


def patched_page(pg):
    return patch.object(service, "get_page", new=AsyncMock(return_value=pg))


class GetPublicAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_enabled_row_yields_public_url(self):
        db = db_with(activation_enabled=True)
        with patched_page(page()), patch.object(settings, "PUBLIC_SITE_HOST", HOST):
            out = await service.get_public_access(db, PAGE_ID)
        self.assertTrue(out["enabled"])
        self.assertEqual(out["host"], HOST)
        self.assertEqual(out["url"], f"https://{HOST}/site/studio/hello")

    async def test_no_row_or_disabled_row_is_not_public(self):
        for value in (None, False):
            db = db_with(activation_enabled=value)
            with patched_page(page()), patch.object(settings, "PUBLIC_SITE_HOST", HOST):
                out = await service.get_public_access(db, PAGE_ID)
            self.assertFalse(out["enabled"])
            self.assertIsNone(out["url"])

    async def test_unconfigured_host_disables_lookup(self):
        db = db_with(activation_enabled=True)
        with patched_page(page()), patch.object(settings, "PUBLIC_SITE_HOST", ""):
            out = await service.get_public_access(db, PAGE_ID)
        self.assertEqual(out, {"enabled": False, "host": None, "url": None})
        self.assertEqual(db._calls, [])  # no activation read without a host


class SetPublicAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_enable_refuses_a_published_tree_with_bound_nodes(self):
        for marker in ("bindings", "card", "repeat"):
            pg = page()
            pg.published_tree = {"type": "section", "children": [{marker: {}}]}
            db = db_with(activation_enabled=False)
            with patched_page(pg), patch.object(settings, "PUBLIC_SITE_HOST", HOST):
                with self.assertRaises(HTTPException) as ctx:
                    await service.set_public_access(db, PAGE_ID, enabled=True, user_id=UID)
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertIn("business data", str(ctx.exception.detail))
            self.assertFalse(any("INSERT INTO site_activation" in sql for sql, _ in db._calls))

    async def test_enable_requires_a_published_page(self):
        for status, published in (("draft", False), ("published", False), ("archived", True)):
            db = db_with(activation_enabled=False)
            with patched_page(page(status=status, published=published)), \
                 patch.object(settings, "PUBLIC_SITE_HOST", HOST):
                with self.assertRaises(HTTPException) as ctx:
                    await service.set_public_access(db, PAGE_ID, enabled=True, user_id=UID)
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertFalse(any("INSERT INTO site_activation" in sql for sql, _ in db._calls))

    async def test_enable_upserts_synthetic_only_activation(self):
        db = db_with(activation_enabled=True)
        token = service.current_tenant_id.set(TID)
        try:
            with patched_page(page()), \
                 patch.object(settings, "PUBLIC_SITE_HOST", HOST), \
                 patch.object(service, "get_settings", new=AsyncMock(return_value={"colors": {"light": {"background": "#FFFFFF"}}})):
                out = await service.set_public_access(db, PAGE_ID, enabled=True, user_id=UID)
        finally:
            service.current_tenant_id.reset(token)
        self.assertTrue(out["enabled"])
        self.assertEqual(out["url"], f"https://{HOST}/site/studio/hello")
        upserts = [(sql, params) for sql, params in db._calls if "INSERT INTO site_activation" in sql]
        self.assertEqual(len(upserts), 1)
        sql, params = upserts[0]
        self.assertIn("ON CONFLICT (host, slug, page_path)", sql)
        self.assertIn("false", sql)  # allow_connected_data pinned False in the statement itself
        self.assertEqual(params["h"], HOST)
        self.assertEqual(params["s"], "studio")
        self.assertEqual(params["p"], "hello")
        self.assertEqual(params["en"], True)
        self.assertEqual(params["tid"], TID)
        self.assertEqual(params["uid"], UID)
        self.assertEqual(json.loads(params["theme"]), {"colors": {"light": {"background": "#FFFFFF"}}})
        db.commit.assert_awaited()

    async def test_disable_is_allowed_without_publish(self):
        db = db_with(activation_enabled=False)
        token = service.current_tenant_id.set(TID)
        try:
            with patched_page(page(status="draft", published=False)), \
                 patch.object(settings, "PUBLIC_SITE_HOST", HOST), \
                 patch.object(service, "get_settings", new=AsyncMock(return_value={})):
                out = await service.set_public_access(db, PAGE_ID, enabled=False, user_id=UID)
        finally:
            service.current_tenant_id.reset(token)
        self.assertFalse(out["enabled"])
        _, params = [c for c in db._calls if "INSERT INTO site_activation" in c[0]][0]
        self.assertEqual(params["en"], False)

    async def test_unconfigured_host_refuses_write(self):
        db = db_with()
        with patched_page(page()), patch.object(settings, "PUBLIC_SITE_HOST", ""):
            with self.assertRaises(HTTPException) as ctx:
                await service.set_public_access(db, PAGE_ID, enabled=True, user_id=UID)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertFalse(any("INSERT INTO site_activation" in sql for sql, _ in db._calls))


def _fake_revision_model():
    # Stand-in for the SitePageRevision ORM model: publish() only needs the
    # .number/.page_id expressions for the next-number select and a callable
    # constructor; real mapper configuration is covered by integration paths.
    from sqlalchemy import literal_column
    fake = MagicMock()
    fake.number = literal_column("1")
    fake.page_id = literal_column("page_id")
    return fake


class PublishThemeRefreshTests(unittest.IsolatedAsyncioTestCase):
    def _published_page(self):
        pg = page()
        pg.draft_tree = {"type": "section", "children": []}
        return pg

    async def test_publish_refreshes_the_activation_theme_snapshot(self):
        pg = self._published_page()
        db = db_with()
        token = service.current_tenant_id.set(TID)
        try:
            with patched_page(pg), \
                 patch.object(settings, "PUBLIC_SITE_HOST", HOST), \
                 patch.object(service, "SitePageRevision", _fake_revision_model()), \
                 patch.object(service, "get_settings", new=AsyncMock(return_value={"colors": {"light": {"background": "#EEEEEE"}}})), \
                 patch.object(service, "check_bound_tree", new=AsyncMock()):
                await service.publish(db, PAGE_ID, UID)
        finally:
            service.current_tenant_id.reset(token)
        updates = [(sql, params) for sql, params in db._calls if "UPDATE site_activation SET theme" in sql]
        self.assertEqual(len(updates), 1)
        _, params = updates[0]
        self.assertEqual(json.loads(params["theme"]), {"colors": {"light": {"background": "#EEEEEE"}}})
        self.assertEqual(params["h"], HOST)
        self.assertEqual(params["s"], "studio")
        self.assertEqual(params["p"], "hello")

    async def test_publish_skips_theme_refresh_without_a_configured_host(self):
        pg = self._published_page()
        db = db_with()
        with patched_page(pg), \
             patch.object(settings, "PUBLIC_SITE_HOST", ""), \
             patch.object(service, "SitePageRevision", _fake_revision_model()), \
             patch.object(service, "check_bound_tree", new=AsyncMock()):
            await service.publish(db, PAGE_ID, UID)
        self.assertFalse(any("site_activation" in sql for sql, _ in db._calls))


class PublicAccessRequestTests(unittest.TestCase):
    def test_request_model_carries_no_host_field(self):
        from app.platform.site.service import PublicAccessIn
        body = PublicAccessIn.model_validate({"enabled": True, "host": "evil.example",
                                              "slug": "other", "allow_connected_data": True})
        self.assertTrue(body.enabled)
        self.assertFalse(hasattr(body, "host"))
        self.assertFalse(hasattr(body, "slug"))
        self.assertFalse(hasattr(body, "allow_connected_data"))
        self.assertEqual(body.model_dump(), {"enabled": True})


class ResponsiveCssTests(unittest.TestCase):
    def test_base_css_stacks_columns_and_tightens_gutters_on_narrow_viewports(self):
        from app.platform.site import render
        css = render._BASE_CSS
        mobile = css.rsplit("@media(max-width:768px)", 1)[-1]
        for cls in (".mz-columns-2", ".mz-columns-3", ".mz-columns-4"):
            self.assertIn(cls, mobile)
        self.assertIn("grid-template-columns:1fr", mobile)
        self.assertIn(".mz-section{padding:24px 16px}", mobile)
        tablet = css.split("@media(max-width:1024px)", 1)[-1]
        self.assertIn(".mz-columns-4", tablet)
        self.assertIn("repeat(2,minmax(0,1fr))", tablet)

    def test_rendered_page_carries_the_media_query(self):
        from app.platform.site import render
        tree = {"type": "section", "id": "s1", "settings": {},
                "children": [{"type": "text", "id": "t1", "content": {"en": {"html": "<p>hi</p>"}}, "settings": {}}]}
        # render_document validates; patch page_problems clean for this CSS-only check.
        with patch("app.platform.site.render.page_problems", return_value=[]):
            html = render.render_document(tree, {"titles": {"en": "Hi"}, "languages": ["en"]},
                                          None, lang="en")
        self.assertIn("@media(max-width:768px)", html)

    def _chrome_html(self, links, link_base=None):
        from app.platform.site import render
        tree = {"type": "section", "id": "s1", "settings": {},
                "children": [{"type": "text", "id": "t1", "content": {"en": {"html": "<p>hi</p>"}}, "settings": {}}]}
        theme = {"header": {"brand": "B", "links": links},
                 "footer": {"lines": ["x"], "links": links}}
        with patch("app.platform.site.render.page_problems", return_value=[]):
            return render.render_document(tree, {"titles": {"en": "Hi"}, "languages": ["en"]},
                                          theme, lang="en", link_base=link_base)

    def test_root_relative_theme_links_resolve_under_the_site_base(self):
        html = self._chrome_html([{"label": "Welcome", "href": "/welcome"}], link_base="/site/studio")
        self.assertIn('href="/site/studio/welcome"', html)
        # Header and footer share the same base handling: two occurrences.
        self.assertEqual(html.count('href="/site/studio/welcome"'), 2)
        self.assertNotIn('href="/welcome"', html)

    def test_theme_links_unchanged_without_link_base(self):
        html = self._chrome_html([{"label": "Welcome", "href": "/welcome"}])
        self.assertIn('href="/welcome"', html)
        self.assertNotIn("/site/studio", html)

    def test_anchor_absolute_and_protocol_relative_links_are_never_rebased(self):
        html = self._chrome_html(
            [{"label": "A", "href": "#top"}, {"label": "B", "href": "https://example.com/x"}],
            link_base="/site/studio")
        self.assertIn('href="#top"', html)
        self.assertIn('href="https://example.com/x"', html)
        self.assertNotIn("/site/studio", html)


if __name__ == "__main__":
    unittest.main()
