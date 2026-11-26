"""Connected-data activation (service.set_connected_data_access).

The separately approved scope: a published, bound page is dry-run through the
same registries and module consent machinery the visitor runtime uses before
allow_connected_data=True is written, with the exact approved source set
pinned. Covers wording acknowledgement, unpublished/unbound refusals, dry-run
failure mapping, disable, widened-source publish refusal, and the public
state readout. DB is mocked like test_public_access.py.
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
from app.framework.storefront_runtime import SourceUnavailable
# Register the auth model classes (UserPosition et al.) that ORM relationships
# pulled in via storefront_runtime resolve against at mapper configuration.
from app.platform.auth.models import user as _auth_models  # noqa: F401
from app.platform.permissions import models as _perm_models  # noqa: F401
from app.platform.site import service

TID = uuid.UUID("a1b975ac-32ac-4813-9b35-e43069616c5f")
UID = uuid.UUID("c3c975ac-32ac-4813-9b35-e43069616c5f")
PAGE_ID = uuid.UUID("d4d975ac-32ac-4813-9b35-e43069616c5f")
HOST = "mizan-studio-feature-test.vercel.app"

BOUND_TREE = {
    "type": "section",
    "children": [{
        "type": "heading",
        "bindings": {"schema": "mizan.page-bindings.v1",
                     "content": {"en": {"text": {"mode": "dynamic", "module": "inventory",
                                                 "source": "products", "field": "name",
                                                 "on_missing": "hide"}}}},
    }],
}


def page(slug="hello", status="published", tree=None):
    p = MagicMock()
    p.slug = slug
    p.status = status
    p.published_tree = tree if tree is not None else BOUND_TREE
    return p


def db_scripted():
    db = AsyncMock()
    calls = []

    async def _exec(stmt, params=None):
        calls.append((str(stmt), params))
        r = MagicMock()
        r.first.return_value = None
        return r

    db.execute.side_effect = _exec
    db._calls = calls
    return db


def enable_patches(pg, resolve_error=None):
    """Everything set_connected_data_access touches beyond the scripted db."""
    patches = [
        patch.object(service, "get_page", new=AsyncMock(return_value=pg)),
        patch.object(service, "check_bound_tree", new=AsyncMock()),
        patch.object(service, "resolved_settings", new=AsyncMock(return_value={"a": 1})),
        patch.object(service, "get_public_access", new=AsyncMock(return_value={"enabled": True})),
        patch.object(settings, "PUBLIC_SITE_HOST", HOST),
        patch("app.framework.activation.get_active_modules", new=AsyncMock(return_value=["inventory"])),
        patch("app.platform.site.storefront.repeats.has_repeat", return_value=False),
        patch("app.platform.site.storefront.card_runtime.has_card", return_value=False),
        patch("app.platform.site.storefront.bindings.resolve_tree",
              new=AsyncMock(side_effect=resolve_error)),
        patch("app.platform.site.storefront.registry.scalar_registry", return_value=MagicMock()),
        patch("app.platform.site.storefront.registry.collection_registry", return_value=MagicMock()),
    ]
    return patches


class ConnectedDataAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_audience_version_refused(self):
        db = db_scripted()
        with patch.object(service, "get_page", new=AsyncMock(return_value=page())):
            with self.assertRaises(HTTPException) as ctx:
                await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                        audience_version="older")
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_unpublished_page_refused(self):
        db = db_scripted()
        with patch.object(service, "get_page", new=AsyncMock(return_value=page(status="draft"))):
            with self.assertRaises(HTTPException) as ctx:
                await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                        audience_version=service.AUDIENCE_POLICY_CONNECTED)
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_unbound_page_refused_to_ordinary_toggle(self):
        db = db_scripted()
        plain = {"type": "section", "children": []}
        with patch.object(service, "get_page", new=AsyncMock(return_value=page(tree=plain))), \
             patch.object(settings, "PUBLIC_SITE_HOST", HOST):
            with self.assertRaises(HTTPException) as ctx:
                await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                        audience_version=service.AUDIENCE_POLICY_CONNECTED)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("ordinary public access", ctx.exception.detail)

    async def test_enable_dry_run_then_insert_pins_sources(self):
        db = db_scripted()
        for p in enable_patches(page()):
            p.start()
        token = service.current_tenant_id.set(TID)
        try:
            out = await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                          audience_version=service.AUDIENCE_POLICY_CONNECTED)
        finally:
            service.current_tenant_id.reset(token)
            patch.stopall()
        self.assertTrue(out["enabled"])
        inserts = [c for c in db._calls if "INSERT INTO site_activation" in c[0]]
        self.assertEqual(len(inserts), 1)
        params = inserts[0][1]
        self.assertEqual(json.loads(params["src"]), ["inventory.products"])
        self.assertEqual(params["apv"], service.AUDIENCE_POLICY_CONNECTED)
        self.assertEqual(params["uid"], UID)

    async def test_enable_dry_run_passes_item_resolver(self):
        """Regression: a page with element item bindings must dry-run with the
        item resolver, or approval always fails 'Element binding source is
        unavailable' (live Phase 3 finding)."""
        db = db_scripted()
        dry_run = AsyncMock()
        patches = [p if not (hasattr(p, 'attribute') and p.attribute == 'resolve_tree')
                   else patch("app.platform.site.storefront.bindings.resolve_tree", new=dry_run)
                   for p in enable_patches(page())]
        for p in patches:
            p.start()
        token = service.current_tenant_id.set(TID)
        try:
            out = await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                          audience_version=service.AUDIENCE_POLICY_CONNECTED)
        finally:
            service.current_tenant_id.reset(token)
            patch.stopall()
        self.assertTrue(out["enabled"])
        args = dry_run.await_args
        self.assertIsNotNone(args.args[4] if len(args.args) > 4 else args.kwargs.get("items"))

    async def test_enable_dry_run_failure_is_422_with_reason(self):
        db = db_scripted()
        for p in enable_patches(page(), resolve_error=SourceUnavailable("consent revoked")):
            p.start()
        token = service.current_tenant_id.set(TID)
        try:
            with self.assertRaises(HTTPException) as ctx:
                await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                        audience_version=service.AUDIENCE_POLICY_CONNECTED)
        finally:
            service.current_tenant_id.reset(token)
            patch.stopall()
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("consent revoked", ctx.exception.detail)
        self.assertFalse(any("INSERT INTO site_activation" in c[0] for c in db._calls))

    async def test_disable_only_touches_managed_rows(self):
        db = db_scripted()
        with patch.object(service, "get_page", new=AsyncMock(return_value=page())), \
             patch.object(settings, "PUBLIC_SITE_HOST", HOST), \
             patch.object(service, "get_public_access", new=AsyncMock(return_value={"enabled": False})):
            out = await service.set_connected_data_access(db, PAGE_ID, enabled=False, user_id=UID,
                                                          audience_version=service.AUDIENCE_POLICY_CONNECTED)
        self.assertFalse(out["enabled"])
        updates = [c for c in db._calls if "UPDATE site_activation" in c[0]]
        self.assertEqual(len(updates), 1)
        self.assertIn("allow_connected_data IS TRUE", updates[0][0])

    async def test_ordinary_disable_preserves_managed_audience_version(self):
        # An ordinary availability disable on a managed row (allow_connected_data)
        # must not overwrite the connected-data audience wording the activation
        # was approved under with the synthetic one: the upsert carries the
        # row's stored version instead.
        db = db_scripted()
        managed_row = MagicMock(enabled=True, allow_connected_data=True,
                                audience_policy_version=service.AUDIENCE_POLICY_CONNECTED)

        async def _exec(stmt, params=None):
            db._calls.append((str(stmt), params))
            r = MagicMock()
            r.first.return_value = managed_row if "FROM site_activation" in str(stmt) else None
            return r

        db.execute.side_effect = _exec
        with patch.object(service, "get_page", new=AsyncMock(return_value=page())), \
             patch.object(settings, "PUBLIC_SITE_HOST", HOST), \
             patch.object(service, "resolved_settings", new=AsyncMock(return_value={"a": 1})), \
             patch.object(service, "get_public_access", new=AsyncMock(return_value={"enabled": False})):
            await service.set_public_access(db, PAGE_ID, enabled=False, user_id=UID)
        writes = [c for c in db._calls if "INSERT INTO site_activation" in c[0]]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][1]["apv"], service.AUDIENCE_POLICY_CONNECTED)
        # The conflict UPDATE still never touches the flag itself.
        self.assertNotIn("allow_connected_data", writes[0][0].split("DO UPDATE", 1)[1])


class PublishGuardTests(unittest.IsolatedAsyncioTestCase):
    """publish() under an enabled connected activation must stay inside the
    approved source set; widening is refused before any mutation."""

    def _db(self, allow_connected, approved):
        db = AsyncMock()
        row = MagicMock(allow_connected_data=allow_connected, approved_sources=approved)

        async def _exec(stmt, params=None):
            r = MagicMock()
            r.first.return_value = row if "FROM site_activation" in str(stmt) else None
            r.scalar.return_value = None
            return r

        db.execute.side_effect = _exec
        db.scalar = AsyncMock(return_value=1)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    def _patches(self, pg, db):
        return [
            patch.object(service, "get_page", new=AsyncMock(return_value=pg)),
            patch.object(service, "check_bound_tree", new=AsyncMock()),
            patch.object(service, "_refresh_activation_theme", new=AsyncMock()),
            patch.object(settings, "PUBLIC_SITE_HOST", HOST),
        ]

    async def test_widening_sources_refused_before_mutation(self):
        pg = page()
        pg.draft_tree = BOUND_TREE
        pg.titles = {"en": "Hello"}
        db = self._db(True, ["inventory.categories"])
        for p in self._patches(pg, db):
            p.start()
        try:
            with self.assertRaises(HTTPException) as ctx:
                await service.publish(db, PAGE_ID, user_id=UID)
        finally:
            patch.stopall()
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("beyond the approved public set", ctx.exception.detail)
        self.assertIn("inventory.products", ctx.exception.detail)
        db.add.assert_not_called()
        db.commit.assert_not_called()

    async def test_within_approved_sources_publishes(self):
        pg = page()
        pg.draft_tree = BOUND_TREE
        pg.titles = {"en": "Hello"}
        pg.edit_token = "x" * 64
        db = self._db(True, ["inventory.products"])
        for p in self._patches(pg, db):
            p.start()
        try:
            out = await service.publish(db, PAGE_ID, user_id=UID)
        finally:
            patch.stopall()
        self.assertEqual(out.status, "published")
        db.commit.assert_called()

    async def test_synthetic_activation_still_refuses_bound_publish(self):
        pg = page()
        pg.draft_tree = BOUND_TREE
        pg.titles = {"en": "Hello"}
        db = self._db(False, [])
        for p in self._patches(pg, db):
            p.start()
        try:
            with self.assertRaises(HTTPException) as ctx:
                await service.publish(db, PAGE_ID, user_id=UID)
        finally:
            patch.stopall()
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("synthetic scope", ctx.exception.detail)
        db.commit.assert_not_called()


class PublicAccessReadoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_managed_row_reports_connected_data_and_sources(self):
        db = AsyncMock()
        row = MagicMock(enabled=True, allow_connected_data=True,
                        approved_sources=["inventory.products"])

        async def _exec(stmt, params=None):
            r = MagicMock()
            r.first.return_value = row
            return r

        db.execute.side_effect = _exec
        with patch.object(service, "get_page", new=AsyncMock(return_value=page())), \
             patch.object(settings, "PUBLIC_SITE_HOST", HOST):
            out = await service.get_public_access(db, PAGE_ID)
        self.assertTrue(out["connected_data"])
        self.assertEqual(out["sources"], ["inventory.products"])

    async def test_synthetic_row_reports_no_connected_data(self):
        db = AsyncMock()
        row = MagicMock(enabled=True, allow_connected_data=False, approved_sources=[])

        async def _exec(stmt, params=None):
            r = MagicMock()
            r.first.return_value = row
            return r

        db.execute.side_effect = _exec
        with patch.object(service, "get_page", new=AsyncMock(return_value=page())), \
             patch.object(settings, "PUBLIC_SITE_HOST", HOST):
            out = await service.get_public_access(db, PAGE_ID)
        self.assertFalse(out["connected_data"])
        self.assertEqual(out["sources"], [])


if __name__ == "__main__":
    unittest.main()


ROUTE_ITEM_TREE = {
    "type": "section",
    "children": [{
        "type": "heading",
        "bindings": {"schema": "mizan.page-bindings.experimental.v2",
                     "content": {"en": {"text": {"mode": "route", "module": "inventory",
                                                 "source": "products", "field": "name",
                                                 "on_missing": "hide"}}}},
    }],
}

ROUTE_CATEGORY_TREE = {
    "type": "section",
    "children": [{
        "type": "columns",
        "children": [{
            "type": "column",
            "repeat": {"schema": "mizan.page-repeat.experimental.v2",
                       "content": {"en": {"template_id": "n_0123456789abcdef", "module": "inventory",
                                          "source": "category_products", "category": "route",
                                          "limit": 8, "on_missing": "hide"}}},
            "children": [],
        }],
    }],
}

PROBE_PRODUCT = str(uuid.UUID("e5f975ac-32ac-4813-9b35-e43069616c5f"))
PROBE_CATEGORY = str(uuid.UUID("f6a975ac-32ac-4813-9b35-e43069616c5f"))


def fake_route_probe(keys_by_ref):
    """registry.route_probe replacement: (kind, module, source) -> record keys."""
    def factory(db):
        async def sample(context, kind, module, source):
            return list(keys_by_ref.get((kind, module, source), ()))
        return sample
    return factory


class RouteProbeDryRunTests(unittest.IsolatedAsyncioTestCase):
    """Gap register item 16: the approval dry-run re-resolves route-parameterized
    reads against real currently-exposable records, so record-driven failures
    refuse the approval instead of first surfacing at visitor request time."""

    async def test_route_item_probe_reruns_resolution_with_record(self):
        db = db_scripted()
        pg = page(tree=ROUTE_ITEM_TREE)
        resolve = AsyncMock(return_value={"type": "section", "children": []})
        patches = enable_patches(pg) + [
            patch("app.platform.site.storefront.bindings.resolve_tree", new=resolve),
            patch("app.platform.site.storefront.registry.route_probe",
                  new=fake_route_probe({("p", "inventory", "products"): [PROBE_PRODUCT]})),
        ]
        for p in patches:
            p.start()
        try:
            token = service.current_tenant_id.set(TID)
            try:
                await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                        audience_version=service.AUDIENCE_POLICY_CONNECTED)
            finally:
                service.current_tenant_id.reset(token)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(resolve.await_count, 2)
        dry_ctx = resolve.await_args_list[0].args[2]
        probe_ctx = resolve.await_args_list[1].args[2]
        self.assertIsNone(dry_ctx.route_item)
        self.assertEqual(probe_ctx.route_item, PROBE_PRODUCT)
        self.assertEqual(probe_ctx.audience, "public")

    async def test_route_probe_failure_refuses_with_reason(self):
        db = db_scripted()
        pg = page(tree=ROUTE_ITEM_TREE)
        resolve = AsyncMock(side_effect=[{"type": "section", "children": []},
                                         SourceUnavailable("Expanded page is not a valid bounded native tree.")])
        patches = enable_patches(pg) + [
            patch("app.platform.site.storefront.bindings.resolve_tree", new=resolve),
            patch("app.platform.site.storefront.registry.route_probe",
                  new=fake_route_probe({("p", "inventory", "products"): [PROBE_PRODUCT]})),
        ]
        for p in patches:
            p.start()
        try:
            token = service.current_tenant_id.set(TID)
            try:
                with self.assertRaises(HTTPException) as ctx:
                    await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                            audience_version=service.AUDIENCE_POLICY_CONNECTED)
            finally:
                service.current_tenant_id.reset(token)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("dynamic template fails when a real published record", ctx.exception.detail)

    async def test_route_probe_skipped_when_nothing_exposable(self):
        db = db_scripted()
        pg = page(tree=ROUTE_ITEM_TREE)
        resolve = AsyncMock(return_value={"type": "section", "children": []})
        patches = enable_patches(pg) + [
            patch("app.platform.site.storefront.bindings.resolve_tree", new=resolve),
            patch("app.platform.site.storefront.registry.route_probe", new=fake_route_probe({})),
        ]
        for p in patches:
            p.start()
        try:
            token = service.current_tenant_id.set(TID)
            try:
                await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                        audience_version=service.AUDIENCE_POLICY_CONNECTED)
            finally:
                service.current_tenant_id.reset(token)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(resolve.await_count, 1)
        self.assertIsNone(resolve.await_args_list[0].args[2].route_item)

    async def test_route_category_probe_reruns_card_resolution(self):
        db = db_scripted()
        pg = page(tree=ROUTE_CATEGORY_TREE)
        resolve_cards = AsyncMock(return_value={"type": "section", "children": []})
        patches = [p for p in enable_patches(pg)
                   if not str(getattr(p, "attribute", "")) == "has_card"] + [
            patch("app.platform.site.storefront.card_runtime.has_card", return_value=True),
            patch("app.platform.site.storefront.card_runtime.resolve_cards", new=resolve_cards),
            patch("app.platform.site.storefront.registry.route_probe",
                  new=fake_route_probe({("c", "inventory", "category_products"): [PROBE_CATEGORY]})),
        ]
        for p in patches:
            p.start()
        try:
            token = service.current_tenant_id.set(TID)
            try:
                await service.set_connected_data_access(db, PAGE_ID, enabled=True, user_id=UID,
                                                        audience_version=service.AUDIENCE_POLICY_CONNECTED)
            finally:
                service.current_tenant_id.reset(token)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(resolve_cards.await_count, 2)
        self.assertIsNone(resolve_cards.await_args_list[0].args[2].route_item)
        self.assertEqual(resolve_cards.await_args_list[1].args[2].route_item, PROBE_CATEGORY)
