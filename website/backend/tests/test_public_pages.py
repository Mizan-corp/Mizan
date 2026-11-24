"""Visitor runtime V1 public route (website_api.routers.public_pages).

Default disabled twice: PUBLIC_SITE_HOST server config AND an enabled
site_activation row for the exact (host, slug, page_path) triple. Covers
host/slug validation and spoofing, server-config host binding, the
enforceable synthetic content boundary (any bound/provider node refused,
off-host destinations refused, tenant business settings never read), tenant
suspension, draft/archive invisibility, generic failure mapping, response
security headers verified against real renderer output, the anonymous rate
limit, and tenant-context isolation under concurrent cross-tenant requests.
DB is mocked except the real renderer/manifest checks; RLS/bypass cleanup on
a real pooled DB and the hosted/anonymous-browser gates (G5) run on the
isolated candidate before activation.
"""
import asyncio
import re
import time
import types
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.core.config import settings
from app.framework.storefront_runtime import ProjectionInvalid, SourceUnavailable
from app.platform.tenancy.context import current_tenant_id
from website_api.routers import public_pages as pp

TID = uuid.UUID("a1b975ac-32ac-4813-9b35-e43069616c5f")
TID2 = uuid.UUID("b2b975ac-32ac-4813-9b35-e43069616c5f")
HOST = "mizan-studio-feature-test.vercel.app"


def make_request(host=HOST, ip="203.0.113.10", forwarded=None):
    headers = {"host": host}
    if forwarded:
        headers["x-forwarded-host"] = forwarded
    return types.SimpleNamespace(headers=headers, client=types.SimpleNamespace(host=ip))


def db_scripted(results):
    """db.execute returns, per call in order, a result whose .first() is the next item."""
    db = AsyncMock()
    items = iter(results)
    calls = []

    async def _exec(stmt, params=None):
        calls.append(params)
        r = MagicMock()
        r.first.return_value = next(items)
        return r

    db.execute.side_effect = _exec
    db.connection.return_value = AsyncMock()
    db._recorded_params = calls
    return db


def activation_row(tstatus="active", tid=TID, allow_data=False, theme=None):
    return MagicMock(tid=tid, tstatus=tstatus, allow_data=allow_data, activation_theme=theme)


def node(i, t, content=None, children=None, **extra):
    d = {"id": i, "type": t, "settings": {}, "content": content or {}}
    if children:
        d["children"] = children
    d.update(extra)
    return d


def plain_tree(**extra):
    col = node("n_c100", "column", children=[node("n_h100", "heading", {"en": {"text": "Hello"}})])
    tree = node("n_r000", "section", children=[node("n_c000", "columns", children=[col])])
    tree.update(extra)
    return tree


CARD_TREE = plain_tree(card={"products": ["p1"]})
REPEAT_TREE = plain_tree(repeat={"collection": "products"})
BINDINGS_TREE = plain_tree(children=[node("n_c000", "columns", children=[
    node("n_c100", "column", children=[
        node("n_h100", "heading", {"en": {"text": "x"}},
             bindings={"schema": "mizan.page-bindings.experimental.v0", "content": {"en": {"text": {}}}})])])])
OFFHOST_IMG_TREE = plain_tree(children=[node("n_c000", "columns", children=[
    node("n_c100", "column", children=[
        node("n_i100", "image", {"en": {"src": "https://cdn.other.com/a.png", "alt": "a"}})])])])
MAILTO_TREE = plain_tree(children=[node("n_c000", "columns", children=[
    node("n_c100", "column", children=[
        node("n_b100", "button", {"en": {"label": "x", "href": "mailto:a@b.c"}})])])])
ONHOST_TREE = plain_tree(children=[node("n_c000", "columns", children=[
    node("n_c100", "column", children=[
        node("n_b100", "button", {"en": {"label": "x", "href": f"https://{HOST}/site/site/home"}}),
        node("n_i100", "image", {"en": {"src": "/static/synthetic.png", "alt": "a"}})])])])

SETTINGS = MagicMock(value={"colors": {"light": {"background": "#FFFFFF"}}})
SYNTH_THEME = {"colors": {"light": {"primary": "#123456"}}, "header": {"brand": "Synthetic Demo"}}


def page_with(tree):
    return MagicMock(slug="home", titles={"en": "Home"}, published_tree=tree)


def ok_script(tree=None, **row_kw):
    """Synthetic mode: bypass on, activation, bypass off, bind, page (settings never read).
    Connected mode (allow_data=True): plus the site_settings select."""
    row = activation_row(**row_kw)
    script = [None, row, None, None, page_with(tree or plain_tree())]
    if row.allow_data:
        script.append(SETTINGS)
    return script


class Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        pp._rate_hits.clear()
        self._saved_host = settings.PUBLIC_SITE_HOST
        settings.PUBLIC_SITE_HOST = HOST

    def tearDown(self):
        settings.PUBLIC_SITE_HOST = self._saved_host

    async def test_route_disabled_without_server_config(self):
        settings.PUBLIC_SITE_HOST = ""
        db = db_scripted([])
        with self.assertRaises(HTTPException) as cm:
            await pp.public_page("site", "home", make_request(), db)
        self.assertEqual(cm.exception.status_code, 404)
        db.execute.assert_not_awaited()

    async def test_host_must_match_server_config_not_only_activation(self):
        # A registered activation host is not enough: the request must arrive
        # through the domain this deployment is configured for.
        settings.PUBLIC_SITE_HOST = "other-registered.example"
        db = db_scripted([])
        with self.assertRaises(HTTPException) as cm:
            await pp.public_page("site", "home", make_request(host=HOST), db)
        self.assertEqual(cm.exception.status_code, 404)
        db.execute.assert_not_awaited()

    async def test_host_normalization_rejects_ports_duplicates_and_case(self):
        self.assertIsNone(pp._public_host(make_request(host="example.test:8443")))
        self.assertIsNone(pp._public_host(make_request(host="a.test,b.test")))
        self.assertIsNone(pp._public_host(make_request(host="")))
        self.assertEqual(pp._public_host(make_request(host="EXAMPLE.Test")), "example.test")

    async def test_forwarded_host_header_is_never_trusted(self):
        req = make_request(host="attacker.invalid", forwarded=HOST)
        self.assertEqual(pp._public_host(req), "attacker.invalid")
        with self.assertRaises(HTTPException) as cm:
            await pp.public_page("site", "home", req, db_scripted([]))
        self.assertEqual(cm.exception.status_code, 404)  # junk host != configured host

    async def test_spoofed_host_cannot_reach_another_tenants_activation(self):
        settings.PUBLIC_SITE_HOST = "evil.example"  # deployment configured for the spoofed name
        db = db_scripted([None, None, None])  # no row for (evil.example, site, home)
        with self.assertRaises(HTTPException) as cm:
            await pp.public_page("site", "home", make_request(host="evil.example"), db)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(db.execute.await_count, 3)

    async def test_activation_is_bound_to_the_exact_page_path(self):
        db = db_scripted([None, None, None])
        with self.assertRaises(HTTPException):
            await pp.public_page("site", "other-page", make_request(), db)
        self.assertEqual(db._recorded_params[1], {"h": HOST, "s": "site", "p": "other-page"})

    async def test_malformed_slug_or_path_is_generic_404(self):
        for slug, path in (("a/b", "home"), ("home", "a.b"), ("ho_me", "home"), ("home", "x" * 81)):
            with self.assertRaises(HTTPException) as cm:
                await pp.public_page(slug, path, make_request(), db_scripted([]))
            self.assertEqual(cm.exception.status_code, 404)

    async def test_default_disabled_is_404_and_never_binds_tenant(self):
        db = db_scripted([None, None, None])
        with self.assertRaises(HTTPException) as cm:
            await pp.public_page("site", "home", make_request(), db)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(db.execute.await_count, 3)  # bypass on, select, bypass off - then stop
        self.assertIsNone(current_tenant_id.get())

    async def test_suspended_workspace_is_404(self):
        db = db_scripted([None, activation_row(tstatus="suspended"), None])
        with self.assertRaises(HTTPException) as cm:
            await pp.public_page("site", "home", make_request(), db)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertIsNone(current_tenant_id.get())

    async def test_draft_or_unknown_page_is_the_same_404(self):
        db = db_scripted([None, activation_row(), None, None, None])
        with self.assertRaises(HTTPException) as cm:
            await pp.public_page("site", "home", make_request(), db)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertIsNone(current_tenant_id.get())

    async def test_synthetic_refuses_every_bound_or_provider_node(self):
        for tree in (CARD_TREE, REPEAT_TREE, BINDINGS_TREE):
            pp._rate_hits.clear()
            db = db_scripted(ok_script(tree))
            with self.assertRaises(HTTPException) as cm:
                await pp.public_page("site", "home", make_request(), db)
            self.assertEqual(cm.exception.status_code, 404)
            self.assertIsNone(current_tenant_id.get())

    async def test_synthetic_refuses_offhost_destinations_and_mailto(self):
        for tree in (OFFHOST_IMG_TREE, MAILTO_TREE):
            pp._rate_hits.clear()
            db = db_scripted(ok_script(tree))
            with self.assertRaises(HTTPException) as cm:
                await pp.public_page("site", "home", make_request(), db)
            self.assertEqual(cm.exception.status_code, 404)

    async def test_synthetic_uses_activation_theme_and_never_reads_business_settings(self):
        db = db_scripted(ok_script(ONHOST_TREE, theme=SYNTH_THEME))
        captured = {}

        async def render(db_, page, theme, tid, canonical):
            captured["theme"] = theme
            return "<html>ok</html>"

        with patch.object(pp, "_render_public", new=render):
            resp = await pp.public_page("site", "home", make_request(), db)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(captured["theme"], SYNTH_THEME)
        # 5 reads: bypass on, activation, bypass off, bind set_config, page. No site_settings.
        self.assertEqual(db.execute.await_count, 5)
        self.assertIsNone(current_tenant_id.get())

    async def test_connected_mode_reads_settings_and_allows_bound_tree(self):
        db = db_scripted(ok_script(CARD_TREE, allow_data=True))
        with patch.object(pp, "_render_public", new=AsyncMock(return_value="<html>ok</html>")):
            resp = await pp.public_page("site", "home", make_request(), db)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(db.execute.await_count, 6)

    async def test_success_returns_html_with_security_headers_and_clears_context(self):
        db = db_scripted(ok_script())
        with patch.object(pp, "_render_public", new=AsyncMock(return_value="<html>ok</html>")):
            resp = await pp.public_page("site", "home", make_request(), db)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, b"<html>ok</html>")
        self.assertEqual(resp.headers["Cache-Control"], "private, no-store")
        self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'none'", resp.headers["Content-Security-Policy"])
        self.assertIsNone(current_tenant_id.get())

    async def test_source_and_projection_failures_are_generic_503_and_clear_context(self):
        for exc in (SourceUnavailable("x"), ProjectionInvalid("y"), ValueError("z")):
            pp._rate_hits.clear()
            db = db_scripted(ok_script())
            with patch.object(pp, "_render_public", new=AsyncMock(side_effect=exc)):
                with self.assertRaises(HTTPException) as cm:
                    await pp.public_page("site", "home", make_request(), db)
            self.assertEqual(cm.exception.status_code, 503)
            self.assertEqual(cm.exception.detail, "Unavailable")
            self.assertIsNone(current_tenant_id.get())

    async def test_rate_limit_blocks_after_window_max(self):
        key = f"198.51.100.7:{HOST}"
        pp._rate_hits[key] = [time.monotonic()] * pp._RATE_MAX_REQUESTS
        db = db_scripted(ok_script())
        with self.assertRaises(HTTPException) as cm:
            await pp.public_page("site", "home", make_request(ip="198.51.100.7"), db)
        self.assertEqual(cm.exception.status_code, 404)
        db.execute.assert_not_awaited()

    async def test_concurrent_cross_tenant_requests_keep_context_isolated(self):
        """Pooled/interleaved requests for two tenants: each render must see its
        own tenant id, a failure in one must not affect the other, and every
        request leaves the context cleared."""
        barrier = asyncio.Event()
        seen = {}

        async def render_a(db, page, theme, tenant_id, canonical):
            seen["a_bind"] = current_tenant_id.get()
            await barrier.wait()  # force overlap with request B
            seen["a_render"] = current_tenant_id.get()
            return "<html>A</html>"

        async def render_b(db, page, theme, tenant_id, canonical):
            seen["b_bind"] = current_tenant_id.get()
            barrier.set()
            await asyncio.sleep(0.02)  # let A resume while B is mid-flight
            seen["b_render"] = current_tenant_id.get()
            raise SourceUnavailable("boom")

        async def run(tid, render, ip):
            db = db_scripted(ok_script(tid=tid))
            with patch.object(pp, "_render_public", new=render):
                return await pp.public_page("site", "home", make_request(ip=ip), db)

        a, b = await asyncio.gather(run(TID, render_a, "203.0.113.1"),
                                    run(TID2, render_b, "203.0.113.2"),
                                    return_exceptions=True)
        self.assertEqual(a.status_code, 200)
        self.assertIsInstance(b, HTTPException)
        self.assertEqual(b.status_code, 503)
        self.assertEqual(seen["a_bind"], TID)
        self.assertEqual(seen["a_render"], TID)
        self.assertEqual(seen["b_bind"], TID2)
        self.assertEqual(seen["b_render"], TID2)
        self.assertIsNone(current_tenant_id.get())

    def test_route_allows_get_and_head_only(self):
        route = next(r for r in pp.router.routes if getattr(r, "path", "") == "/site/{slug}/{page_path}")
        self.assertEqual(set(route.methods), {"GET", "HEAD"})

    def test_migration_registers_default_disabled_rls_table(self):
        from app.db import migrations
        src = open(migrations.__file__, encoding="utf8").read()
        self.assertIn("v112_site_activation", src)
        self.assertIn("enabled boolean NOT NULL DEFAULT false", src)
        self.assertIn("allow_connected_data boolean NOT NULL DEFAULT false", src)
        self.assertIn("theme jsonb", src)
        self.assertIn("uq_site_activation_host_slug_page", src)
        self.assertIn("CREATE POLICY tenant_isolation ON site_activation", src)


class RealRendererChecks(unittest.TestCase):
    """Escaping and CSP verified against the actual render_document output,
    not mocks: hostile content in text, labels, alt text, titles and
    descriptions must be inert, and every asset the renderer emits must be
    permitted by the route's CSP."""

    def _doc(self):
        from app.platform.site.render import render_document

        kids = [
            node("n_h100", "heading", {"en": {"text": "<script>alert(1)</script> H & 'O'"}}),
            node("n_t100", "text", {"en": {"html": 'B <img src=x onerror=alert(2)> <b onclick=alert(3)>x</b> <a href="javascript:alert(4)">y</a>'}}),
            node("n_b100", "button", {"en": {"label": "Order</a><script>x</script>", "href": "https://shop.example.com/x"}}),
            node("n_i100", "image", {"en": {"src": "https://cdn.example.com/a.png", "alt": "<b onmouseover=alert(6)>a</b>"}}),
        ]
        tree = node("n_r000", "section", children=[node("n_c000", "columns", children=[node("n_c100", "column", children=kids)])])
        meta = {"canonical": "https://h.test/site/s/p",
                "titles": {"en": "T</title><script>alert(8)</script>"},
                "descriptions": {"en": 'D"><script>alert(9)</script>'},
                "languages": ["en"]}
        return render_document(tree, meta, {"colors": {"light": {"background": "#FFFFFF"}}}, lang="en")

    def test_hostile_content_is_inert_in_real_output(self):
        html = self._doc()
        for pat in ("<script>alert", "onerror=", "onclick=", "</title><script",
                    "javascript:alert", "Order</a><script", 'D"><script'):
            self.assertNotIn(pat, html, pat)
        # Alt text may keep the literal word, but only entity-escaped inside the attribute.
        self.assertIn("&lt;b onmouseover=alert(6)&gt;", html)

    def test_manifest_rejects_hostile_urls_before_render(self):
        from app.framework.manifest import page_problems

        tree = {"id": "n_r000", "type": "section", "settings": {}, "content": {}, "children": [
            {"id": "n_c000", "type": "columns", "settings": {}, "content": {}, "children": [
                {"id": "n_c100", "type": "column", "settings": {}, "content": {}, "children": [
                    node("n_b100", "button", {"en": {"label": "x", "href": "javascript:alert(5)"}}),
                    node("n_i100", "image", {"en": {"src": "data:text/html,<script>alert(7)</script>", "alt": "a"}}),
                    node("n_v100", "video_embed", {"en": {"url": "https://evil.example.com/embed"}}),
                ]}]}]}
        problems = page_problems(tree, ("en", "ar"))
        self.assertGreaterEqual(len(problems), 3)

    def test_csp_permits_every_asset_the_renderer_emits(self):
        html = self._doc()
        csp = pp._HEADERS["Content-Security-Policy"]
        self.assertEqual(re.findall(r"<script[^>]*>", html), [])  # no JS at all
        self.assertIn("style-src 'unsafe-inline'", csp)  # inline theme <style> blocks exist
        self.assertGreater(len(re.findall(r"<style", html)), 0)
        for src in re.findall(r"<img[^>]*src=\"([^\"]+)\"", html):
            self.assertTrue(src.startswith("https://") or src.startswith("/"),
                            f"img not covered by img-src 'self' https:: {src}")
        self.assertNotIn("data:", " ".join(re.findall(r'src="([^"]+)"', html)))
        allowed = ("https://www.youtube.com/", "https://www.youtube-nocookie.com/",
                   "https://www.google.com/", "https://maps.google.com/")
        for f in re.findall(r"<iframe[^>]*src=\"([^\"]+)\"", html):
            self.assertTrue(f.startswith(allowed), f"frame outside CSP frame-src: {f}")


if __name__ == "__main__":
    unittest.main()
