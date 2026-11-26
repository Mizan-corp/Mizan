"""v4 consent scope (docs/studio-consent-scope-v4.md): description field,
category membership linkage, and the v4 writer payload shape.

Real models and real SQLAlchemy statements over a mocked session; not a live
database integration. Pins: older wordings never unlock description or
linkage; v4 requires its exact six-key payload; the description column is
selected only after the explicit show_description opt-in; over-bound
descriptions fail closed; category reads require a recorded v4 policy AND a
published category, and revoked products never reach the query.
"""
import json
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock

import os, sys
from pathlib import Path
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY', 'offline-test-not-used-for-signing')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.registry import load_all_models
load_all_models()
from app.activities.general.modules.inventory.storefront import cards as c
from app.activities.general.modules.inventory.storefront import provider as p
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.platform.tenancy.context import current_tenant_id

A = uuid.UUID('a1b975ac-32ac-4813-9b35-e43069616c5f')
P1 = uuid.UUID('b2c075bd-43bd-5924-a645-d53079717d60')
P2 = uuid.UUID('c3d186ce-54ce-6a35-b756-e64180828e71')
CAT = uuid.UUID('d4e297df-65df-7b46-c867-f75291939f82')


def policy(schema, products, show_description=None, **kw):
    value = {'schema': schema, 'products': [str(x) for x in products],
             'show_price': kw.get('show_price', False),
             'show_image': kw.get('show_image', False),
             'currency': kw.get('currency')}
    if show_description is not None:
        value['show_description'] = show_description
    return json.dumps(value)


def publication(categories):
    return json.dumps({'schema': p.SCHEMA, 'products': [],
                       'categories': [str(x) for x in categories]})


def first_row(*values):
    r = MagicMock()
    r.first.return_value = values
    return r


def all_rows(*rows_):
    r = MagicMock()
    r.all.return_value = list(rows_)
    return r


class DescriptionScopeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.ctx = SourceContext(A, 'en', frozenset({'inventory'}))
        self.db = AsyncMock()

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_v3_row_never_unlocks_description(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V3, [P1])
        self.db.execute.return_value = first_row(P1, 'Widget')
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name', 'description'))
        self.assertEqual(item['description'], None)
        # The description column was not even selected.
        stmt = self.db.execute.call_args.args[0]
        self.assertEqual(len(stmt.selected_columns), 2)

    async def test_v4_without_show_description_selects_no_description(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V4, [P1], show_description=False)
        self.db.execute.return_value = first_row(P1, 'Widget')
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name', 'description'))
        self.assertEqual(item['description'], None)
        stmt = self.db.execute.call_args.args[0]
        self.assertEqual(len(stmt.selected_columns), 2)

    async def test_v4_with_show_description_returns_bounded_text(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V4, [P1], show_description=True)
        self.db.execute.return_value = first_row(P1, 'Widget', 'A plain description.')
        item = await c.read_scoped_item(self.db, self.ctx, str(P1), ('name', 'description'))
        self.assertEqual(item['description'], 'A plain description.')

    async def test_over_bound_description_fails_closed(self):
        self.db.scalar.return_value = policy(c.SCHEMA_V4, [P1], show_description=True)
        self.db.execute.return_value = first_row(P1, 'Widget', 'x' * 2001)
        with self.assertRaises(SourceUnavailable):
            await c.read_scoped_item(self.db, self.ctx, str(P1), ('name', 'description'))

    async def test_v4_payload_requires_exact_six_keys(self):
        with self.assertRaises(SourceUnavailable):
            c.card_policy(policy(c.SCHEMA_V4, [P1]), schema=c.SCHEMA_V4)  # missing show_description
        with self.assertRaises(SourceUnavailable):
            c.card_policy(policy(c.SCHEMA_V4, [P1], show_description='yes'), schema=c.SCHEMA_V4)
        ok = c.card_policy(policy(c.SCHEMA_V4, [P1], show_description=True), schema=c.SCHEMA_V4)
        self.assertEqual(ok['show_description'], True)

    async def test_older_schemas_read_description_as_refused(self):
        for schema in (c.SCHEMA, c.SCHEMA_V1, c.SCHEMA_V2, c.SCHEMA_V3):
            ok = c.card_policy(policy(schema, [P1]), schema=schema)
            self.assertEqual(ok['show_description'], False)

    async def test_public_audience_accepts_v4_for_elements(self):
        ctx = SourceContext(A, 'en', frozenset({'inventory'}), audience='public')
        self.db.scalar.return_value = policy(c.SCHEMA_V4, [P1], show_description=True)
        self.db.execute.return_value = first_row(P1, 'Widget', 'Public-safe text.')
        item = await c.read_scoped_item(self.db, ctx, str(P1), ('name', 'description'))
        self.assertEqual(item['description'], 'Public-safe text.')


class CategoryLinkageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.ctx = SourceContext(A, 'en', frozenset({'inventory'}))
        self.db = AsyncMock()

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_older_consent_never_reveals_linkage(self):
        for schema in (c.SCHEMA, c.SCHEMA_V1, c.SCHEMA_V2, c.SCHEMA_V3):
            self.db.scalar = AsyncMock(side_effect=[policy(schema, [P1])])
            self.assertEqual(await c.read_category_products(self.db, self.ctx, str(CAT), 24), [])
            self.db.execute.assert_not_called()

    async def test_unpublished_category_returns_nothing(self):
        self.db.scalar = AsyncMock(side_effect=[
            policy(c.SCHEMA_V4, [P1], show_description=False),
            publication([]),  # category not in the allowlist
        ])
        self.assertEqual(await c.read_category_products(self.db, self.ctx, str(CAT), 24), [])
        self.db.execute.assert_not_called()

    async def test_published_category_returns_consented_members_only(self):
        self.db.scalar = AsyncMock(side_effect=[
            policy(c.SCHEMA_V4, [P1], show_description=False),
            publication([CAT]),
        ])
        self.db.execute.return_value = all_rows((P1, 'In category'))
        rows = await c.read_category_products(self.db, self.ctx, str(CAT), 24)
        self.assertEqual(rows, [{'item_key': str(P1), 'name': 'In category', 'price': None, 'image': None}])
        stmt = self.db.execute.call_args.args[0]
        from sqlalchemy.sql import Join
        self.assertTrue(any(isinstance(f, Join) for f in stmt.get_final_froms()))

    async def test_malformed_category_identity_fails_closed(self):
        for bad in ('not-a-uuid', str(CAT).upper(), '', 42):
            with self.assertRaises(SourceUnavailable):
                await c.read_category_products(self.db, self.ctx, bad, 24)

    async def test_limit_bound_enforced(self):
        for bad in (0, 25, '24'):
            with self.assertRaises(SourceUnavailable):
                await c.read_category_products(self.db, self.ctx, str(CAT), bad)


B = uuid.UUID('e5f3a80e-76e0-8c57-d968-a053a04a91a3')
FOREIGN_CAT = uuid.UUID('f604b91f-87f1-9d68-ea79-b164b15b02b4')
FOREIGN_PROD = uuid.UUID('0715ca20-9802-ae79-fb8a-c275c26c13c5')


def where_sql(stmt):
    # literal_binds renders UUID values in hex form without dashes.
    return str(stmt.compile(compile_kwargs={'literal_binds': True}))


class CrossTenantIsolationTests(unittest.IsolatedAsyncioTestCase):
    """Negative regression (2026-11-25): the fixtures database holds
    duplicate-named categories across tenants, and a tenant-blind ad-hoc
    lookup once picked another tenant's category during E2E authoring. These
    tests pin that visitor-facing reads can never cross tenants: consent,
    publication and record queries are all scoped by context.tenant_id, a
    mismatched tenant context fails closed, and foreign-tenant identities
    resolve to nothing. No leak was observed; this guards the boundary."""

    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.ctx = SourceContext(A, 'en', frozenset({'inventory'}), audience='public')
        self.db = AsyncMock()

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_tenant_context_mismatch_fails_closed(self):
        current_tenant_id.reset(self.t)
        self.t = current_tenant_id.set(B)  # request tenant != source context tenant
        with self.assertRaises(SourceUnavailable):
            await c.read_category_products(self.db, self.ctx, str(CAT), 24)
        with self.assertRaises(SourceUnavailable):
            await c.read_route_item(self.db, self.ctx, str(P1), ('name',))
        self.db.scalar.assert_not_called()
        self.db.execute.assert_not_called()

    async def test_category_read_queries_are_tenant_scoped(self):
        self.db.scalar = AsyncMock(side_effect=[
            policy(c.SCHEMA_V4, [P1], show_description=False),
            publication([CAT]),
        ])
        self.db.execute.return_value = all_rows((P1, 'In category'))
        rows = await c.read_category_products(self.db, self.ctx, str(CAT), 24)
        self.assertEqual(len(rows), 1)
        # Consent policy and publication allowlist come only from this tenant's rows.
        for call in self.db.scalar.call_args_list:
            sql = where_sql(call.args[0])
            self.assertIn('store_settings.tenant_id', sql)
            self.assertIn(A.hex, sql)
            self.assertNotIn(B.hex, sql)
        product_sql = where_sql(self.db.execute.call_args.args[0])
        self.assertIn('products.tenant_id', product_sql)
        self.assertIn(A.hex, product_sql)

    async def test_foreign_tenant_category_returns_nothing(self):
        # A category id that exists only under another tenant can never enter
        # this tenant's publication allowlist (the choices router lists only
        # own-tenant records), so the visitor read returns empty.
        self.db.scalar = AsyncMock(side_effect=[
            policy(c.SCHEMA_V4, [P1], show_description=False),
            publication([CAT]),  # own allowlist; FOREIGN_CAT is not in it
        ])
        self.assertEqual(await c.read_category_products(self.db, self.ctx, str(FOREIGN_CAT), 24), [])
        self.db.execute.assert_not_called()

    async def test_foreign_tenant_product_returns_none(self):
        # URL-selected detail read with another tenant's product id: never in
        # this tenant's consent list, so no record row is even queried.
        self.db.scalar = AsyncMock(return_value=policy(c.SCHEMA_V4, [P1], show_description=False))
        self.assertIsNone(await c.read_route_item(self.db, self.ctx, str(FOREIGN_PROD), ('name',)))
        self.db.execute.assert_not_called()

    async def test_item_row_query_is_tenant_scoped(self):
        self.db.scalar = AsyncMock(return_value=policy(c.SCHEMA_V4, [P1], show_description=False))
        self.db.execute.return_value = first_row(P1, 'Widget')
        item = await c.read_route_item(self.db, self.ctx, str(P1), ('name',))
        self.assertEqual(item['name'], 'Widget')
        sql = where_sql(self.db.execute.call_args.args[0])
        self.assertIn('products.tenant_id', sql)
        self.assertIn(A.hex, sql)



class RouteCategoryAvailabilityTests(unittest.IsolatedAsyncioTestCase):
    """The visitor-notice gate (route_category_available): one False for every
    unavailable cause, True only for a v4-consented, allowlisted category -
    including an allowlisted category with zero products, whose empty list is
    a legitimate render rather than a missing record."""
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.ctx = SourceContext(A, 'en', frozenset({'inventory'}))
        self.db = AsyncMock()

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_allowlisted_category_is_available(self):
        self.db.scalar = AsyncMock(side_effect=[
            policy(c.SCHEMA_V4, [P1], show_description=False),
            publication([CAT]),
        ])
        self.assertTrue(await c.route_category_available(self.db, self.ctx, str(CAT)))

    async def test_unpublished_category_is_unavailable(self):
        self.db.scalar = AsyncMock(side_effect=[
            policy(c.SCHEMA_V4, [P1], show_description=False),
            publication([]),
        ])
        self.assertFalse(await c.route_category_available(self.db, self.ctx, str(CAT)))

    async def test_older_consent_is_unavailable(self):
        for schema in (c.SCHEMA, c.SCHEMA_V1, c.SCHEMA_V2, c.SCHEMA_V3):
            self.db.scalar = AsyncMock(side_effect=[policy(schema, [P1])])
            self.assertFalse(await c.route_category_available(self.db, self.ctx, str(CAT)))

    async def test_no_policy_row_is_unavailable(self):
        self.db.scalar = AsyncMock(side_effect=[None])
        self.assertFalse(await c.route_category_available(self.db, self.ctx, str(CAT)))

    async def test_malformed_identity_fails_closed(self):
        for bad in ('not-a-uuid', str(CAT).upper(), '', 42):
            with self.assertRaises(SourceUnavailable):
                await c.route_category_available(self.db, self.ctx, bad)

    async def test_tenant_context_mismatch_fails_closed(self):
        ctx = SourceContext(B, 'en', frozenset({'inventory'}))
        with self.assertRaises(SourceUnavailable):
            await c.route_category_available(self.db, ctx, str(CAT))


class RouteAvailabilityDispatchTests(unittest.IsolatedAsyncioTestCase):
    """registry.route_availability dispatches to the same consent-checked
    readers the render uses; unknown kinds are never available."""
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.ctx = SourceContext(A, 'en', frozenset({'inventory'}), audience='public',
                                 route_item=str(P1))

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_dispatch_and_unknown_kind(self):
        from app.platform.site.storefront import registry
        from unittest.mock import patch
        check = registry.route_availability(AsyncMock())
        with patch.object(c, 'read_route_item', new=AsyncMock(return_value={'name': 'X'})) as rd, \
             patch.object(c, 'route_category_available', new=AsyncMock(return_value=True)) as rc:
            self.assertTrue(await check(self.ctx, 'p', str(P1)))
            self.assertTrue(await check(self.ctx, 'c', str(CAT)))
            rd.assert_awaited_once()
            rc.assert_awaited_once()
        self.assertFalse(await check(self.ctx, 'x', str(P1)))

    async def test_missing_product_is_unavailable(self):
        from app.platform.site.storefront import registry
        from unittest.mock import patch
        check = registry.route_availability(AsyncMock())
        with patch.object(c, 'read_route_item', new=AsyncMock(return_value=None)):
            self.assertFalse(await check(self.ctx, 'p', str(P1)))


if __name__ == '__main__':
    unittest.main()
