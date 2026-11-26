"""Visitor form submissions (contact-form V1): POST /forms/{slug}/{page}/{node}.

Pins: host/slug/node strictly validated (404, no DB read); honeypot answers a
fake success and stores nothing; the node id must resolve to a form block in
the page's own published tree; posted keys must be exactly the fields that
block had enabled; payloads are length-capped and email/message required; a
real submission is stored and answered with a 303 back to the page.
DB is mocked like test_public_item_routes.py.
"""
import types
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock

import os, sys
from pathlib import Path
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY', 'offline-test-not-used-for-signing')
os.environ.setdefault('PUBLIC_SITE_HOST', 'sites.example')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'shared' / 'backend'))

from app.platform.tenancy.context import current_tenant_id
from website_api.routers import public_forms as pf
from website_api.routers import public_pages as pp

TID = uuid.UUID("a1b975ac-32ac-4813-9b35-e43069616c5f")
PAGE_ID = uuid.UUID("c3d186ce-54ce-6035-b756-e64189827e71")
HOST = "sites.example"

FORM_TREE = {
    "id": "n_root1", "type": "section", "settings": {"desktop": {}}, "content": {},
    "children": [{
        "id": "n_cols01", "type": "columns", "settings": {"desktop": {}}, "content": {},
        "children": [{
            "id": "n_col001", "type": "column", "settings": {}, "content": {},
            "children": [{
                "id": "n_form01", "type": "form",
                "settings": {"desktop": {"visible": True, "field_name": True, "field_phone": False}},
                "content": {"en": {"title": "Contact us"}},
            }],
        }],
    }],
}


def make_request(host=HOST, ip="203.0.113.10", form=None, query=None):
    async def _form():
        return form or {}
    return types.SimpleNamespace(headers={"host": host}, client=types.SimpleNamespace(host=ip),
                                 query_params=query or {}, form=_form)


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


def activation_row():
    return MagicMock(tid=TID, tstatus="active", allow_data=False, activation_theme={})


def page_row(tree=FORM_TREE):
    return MagicMock(id=PAGE_ID, published_tree=tree)


def ok_script(tree=FORM_TREE):
    # Bypass on, activation, bypass off, bind, page (same shape as
    # test_public_item_routes.ok_script).
    return [None, activation_row(), None, None, page_row(tree)]


GOOD_FORM = {"name": "Ammar", "email": "ammar@example.com", "message": "hello", "website": ""}


class PublicFormTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        pf._form_hits.clear()
        self._saved_host = pp.settings.PUBLIC_SITE_HOST
        pp.settings.PUBLIC_SITE_HOST = HOST

    def tearDown(self):
        pp.settings.PUBLIC_SITE_HOST = self._saved_host

    async def test_bad_host_slug_and_node_id_are_generic_404_without_db(self):
        db = AsyncMock()
        for slug, path, node in (("Bad_Slug", "contact", "n_form01"), ("site", "x" * 81, "n_form01"),
                                 ("site", "contact", "not-a-node"), ("site", "contact", 'n_bad"x')):
            with self.assertRaises(pf.HTTPException) as cm:
                await pf.submit_form(slug, path, node, make_request(form=GOOD_FORM), db)
            self.assertEqual(cm.exception.status_code, 404, (slug, path, node))
        db.execute.assert_not_called()

    async def test_honeypot_gets_fake_success_and_stores_nothing(self):
        db = AsyncMock()
        res = await pf.submit_form("site", "contact", "n_form01",
                                   make_request(form={**GOOD_FORM, "website": "http://spam"}), db)
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/site/site/contact?form_sent=n_form01")
        db.execute.assert_not_called()
        db.add.assert_not_called()

    async def test_successful_submission_is_stored_and_redirects(self):
        db = db_scripted(ok_script())
        res = await pf.submit_form("site", "contact", "n_form01",
                                   make_request(form=GOOD_FORM, query={"lang": "en"}), db)
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/site/site/contact?form_sent=n_form01&lang=en")
        self.assertEqual(db.add.call_count, 1)
        stored = db.add.call_args.args[0]
        self.assertEqual(stored.page_id, PAGE_ID)
        self.assertEqual(stored.block_id, "n_form01")
        self.assertEqual(stored.payload,
                         {"name": "Ammar", "email": "ammar@example.com", "message": "hello"})
        db.commit.assert_awaited()

    async def test_unknown_node_id_is_404(self):
        db = db_scripted(ok_script())
        with self.assertRaises(pf.HTTPException) as cm:
            await pf.submit_form("site", "contact", "n_form99", make_request(form=GOOD_FORM), db)
        self.assertEqual(cm.exception.status_code, 404)

    async def test_node_that_is_not_a_form_is_404(self):
        tree = {"id": "n_root1", "type": "section", "settings": {"desktop": {}}, "content": {},
                "children": [{"id": "n_cols01", "type": "columns", "settings": {"desktop": {}}, "content": {},
                              "children": [{"id": "n_col001", "type": "column", "settings": {}, "content": {},
                                            "children": [{"id": "n_text01", "type": "text", "settings": {},
                                                          "content": {"en": {"html": "<p>hi</p>"}}}]}]}]}
        db = db_scripted(ok_script(tree))
        with self.assertRaises(pf.HTTPException) as cm:
            await pf.submit_form("site", "contact", "n_text01", make_request(form=GOOD_FORM), db)
        self.assertEqual(cm.exception.status_code, 404)

    async def test_extra_and_missing_keys_are_rejected(self):
        for form in ({**GOOD_FORM, "subject": "hi"},
                     {k: v for k, v in GOOD_FORM.items() if k != "message"},
                     {**GOOD_FORM, "email": ""},
                     {**GOOD_FORM, "email": "not-an-email"}):
            db = db_scripted(ok_script())
            pf._form_hits.clear()
            with self.assertRaises(pf.HTTPException) as cm:
                await pf.submit_form("site", "contact", "n_form01", make_request(form=form), db)
            self.assertEqual(cm.exception.status_code, 400, form)
            db.add.assert_not_called()

    async def test_disabled_fields_are_not_accepted(self):
        # field_name off in the tree: posting a name key is an exact-key mismatch.
        tree = {"id": "n_root1", "type": "section", "settings": {"desktop": {}}, "content": {},
                "children": [{"id": "n_cols01", "type": "columns", "settings": {"desktop": {}}, "content": {},
                              "children": [{"id": "n_col001", "type": "column", "settings": {}, "content": {},
                                            "children": [{"id": "n_form01", "type": "form",
                                                          "settings": {"desktop": {"visible": True, "field_name": False}},
                                                          "content": {"en": {}}}]}]}]}
        db = db_scripted(ok_script(tree))
        with self.assertRaises(pf.HTTPException) as cm:
            await pf.submit_form("site", "contact", "n_form01", make_request(form=GOOD_FORM), db)
        self.assertEqual(cm.exception.status_code, 400)
        db.add.assert_not_called()

    async def test_rate_limit_locks_out_after_ten(self):
        db = db_scripted(ok_script())
        for _ in range(10):
            db2 = db_scripted(ok_script())
            await pf.submit_form("site", "contact", "n_form01", make_request(form=GOOD_FORM), db2)
        with self.assertRaises(pf.HTTPException) as cm:
            await pf.submit_form("site", "contact", "n_form01", make_request(form=GOOD_FORM), db)
        self.assertEqual(cm.exception.status_code, 404)
        db.execute.assert_not_called()

    async def test_tenant_context_is_cleared_afterwards(self):
        db = db_scripted(ok_script())
        await pf.submit_form("site", "contact", "n_form01", make_request(form=GOOD_FORM), db)
        self.assertIsNone(current_tenant_id.get())


if __name__ == "__main__":
    unittest.main()
