"""Visitor dynamic template routes (Phase 3): /site/{slug}/{page}/{p|c}/{uuid}.

Pins: kind and item_id are strictly validated (404, no DB read); the same
(host, slug, page_path) activation row governs item URLs; the normalized UUID
reaches _render_public as route_item; the canonical carries the item suffix.
DB is mocked like test_public_pages.py.
"""
import types
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import os, sys
from pathlib import Path
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY', 'offline-test-not-used-for-signing')
os.environ.setdefault('PUBLIC_SITE_HOST', 'sites.example')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'shared' / 'backend'))

from app.platform.tenancy.context import current_tenant_id
from website_api.routers import public_pages as pp

TID = uuid.UUID("a1b975ac-32ac-4813-9b35-e43069616c5f")
PID = uuid.UUID("b2c075bd-43bd-5924-a645-d53079717d60")
HOST = "sites.example"


def make_request(host=HOST, ip="203.0.113.10"):
    return types.SimpleNamespace(headers={"host": host}, client=types.SimpleNamespace(host=ip),
                                 query_params={})


def db_scripted(results):
    db = AsyncMock()
    items = iter(results)

    async def _exec(stmt, params=None):
        r = MagicMock()
        r.first.return_value = next(items)
        return r

    db.execute.side_effect = _exec
    db.connection.return_value = AsyncMock()
    return db


def ok_script():
    # Bypass on, activation, bypass off, bind, page (same shape as
    # test_public_pages.ok_script).
    page = MagicMock(slug="product", titles={"en": "Product"}, published_tree={"id": "n_r", "type": "section"})
    return [None, pp_row(), None, None, page]


def pp_row():
    return MagicMock(tid=TID, tstatus="active", allow_data=True, activation_theme={})


class PublicItemRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        pp._rate_hits.clear()

    async def test_unknown_kind_and_bad_uuid_are_generic_404_without_db(self):
        db = AsyncMock()
        for kind, item in (("x", str(PID)), ("p", "not-a-uuid"), ("c", "../../etc"), ("p", "")):
            with self.assertRaises(pp.HTTPException) as cm:
                await pp.public_page_item("site", "product", kind, item, make_request(), db)
            self.assertEqual(cm.exception.status_code, 404)
        db.execute.assert_not_called()

    async def test_activation_row_governs_item_urls(self):
        db = db_scripted([None, None, None])  # bypass on, no activation row, bypass off
        with self.assertRaises(pp.HTTPException) as cm:
            await pp.public_page_item("site", "product", "p", str(PID), make_request(), db)
        self.assertEqual(cm.exception.status_code, 404)

    async def test_route_item_and_canonical_reach_render(self):
        db = db_scripted(ok_script())
        seen = {}

        async def render(db_, page, theme, tid, canonical, link_base=None, query=None,
                         lang_override=None, route_item=None):
            seen.update(canonical=canonical, route_item=route_item, tid=tid)
            return "<html>ok</html>"

        with patch.object(pp, "_render_public", new=render):
            resp = await pp.public_page_item("site", "product", "p", str(PID).upper(), make_request(), db)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(seen["route_item"], str(PID))
        self.assertEqual(seen["canonical"], f"https://{HOST}/site/site/product/p/{PID}")
        self.assertEqual(seen["tid"], TID)
        self.assertIsNone(current_tenant_id.get())

    async def test_category_kind_canonical(self):
        db = db_scripted(ok_script())
        seen = {}

        async def render(db_, page, theme, tid, canonical, link_base=None, query=None,
                         lang_override=None, route_item=None):
            seen["canonical"] = canonical
            return "<html>ok</html>"

        with patch.object(pp, "_render_public", new=render):
            await pp.public_page_item("site", "shop", "c", str(PID), make_request(), db)
        self.assertEqual(seen["canonical"], f"https://{HOST}/site/site/shop/c/{PID}")


if __name__ == '__main__':
    unittest.main()
