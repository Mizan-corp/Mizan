"""Phase 3 dynamic templates: URL-selected current-record bindings and
route-category collection source (docs/studio-gap-register.md).

Real models and real SQLAlchemy statements over a mocked session; not a live
database integration. Pins: route-selected reads require a RECORDED v4 policy
for every audience (v0-v3 wordings never named URL-selected retrieval); the
record id comes only from SourceContext.route_item (server-set from the
validated URL segment); absent route items resolve to None (element hides);
revoked/unconsented/inactive records fail closed; the category_products
collection is empty without a route item and otherwise delegates to the v4
category gate.
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
from app.framework import manifest
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.platform.site.storefront.item_bindings import ScopedItems
from app.platform.tenancy.context import current_tenant_id

A = uuid.UUID('a1b975ac-32ac-4813-9b35-e43069616c5f')
P1 = uuid.UUID('b2c075bd-43bd-5924-a645-d53079717d60')
P2 = uuid.UUID('c3d186ce-54ce-6a35-b756-e64180828e71')
CAT = uuid.UUID('d4e297df-65df-7b46-c867-f75291939f82')


def policy(schema, products, **kw):
    value = {'schema': schema, 'products': [str(x) for x in products],
             'show_price': kw.get('show_price', False),
             'show_image': kw.get('show_image', False),
             'currency': kw.get('currency')}
    if schema == c.SCHEMA_V4:
        value['show_description'] = kw.get('show_description', False)
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


def route_binding(field, on_missing='hide'):
    return {'mode': 'route', 'module': 'inventory', 'source': 'products',
            'field': field, 'on_missing': on_missing}


class RouteItemReadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.ctx = SourceContext(A, 'en', frozenset({'inventory'}), route_item=str(P1))

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    def db(self, scalars=(), result=None):
        db = AsyncMock()
        db.scalar = AsyncMock(side_effect=list(scalars))
        db.execute = AsyncMock(return_value=result if result is not None else first_row())
        return db

    async def test_v4_recorded_consent_reads_the_url_selected_record(self):
        db = self.db(scalars=[policy(c.SCHEMA_V4, [P1])], result=first_row(P1, 'Screen'))
        item = await c.read_route_item(db, self.ctx, str(P1), ('name',))
        self.assertEqual(item['name'], 'Screen')

    async def test_older_recorded_wordings_never_authorize_url_selected_reads(self):
        for schema in (c.SCHEMA, c.SCHEMA_V1, c.SCHEMA_V2, c.SCHEMA_V3):
            db = self.db(scalars=[policy(schema, [P1])], result=first_row(P1, 'Screen'))
            self.assertIsNone(await c.read_route_item(db, self.ctx, str(P1), ('name',)))
            db.execute.assert_not_called()

    async def test_public_audience_also_requires_v4(self):
        ctx = SourceContext(A, 'en', frozenset({'inventory'}), audience='public', route_item=str(P1))
        db = self.db(scalars=[policy(c.SCHEMA_V3, [P1])])
        self.assertIsNone(await c.read_route_item(db, ctx, str(P1), ('name',)))
        db2 = self.db(scalars=[policy(c.SCHEMA_V4, [P1])], result=first_row(P1, 'Screen'))
        self.assertIsNotNone(await c.read_route_item(db2, ctx, str(P1), ('name',)))

    async def test_unconsented_inactive_and_missing_records_hide(self):
        db = self.db(scalars=[policy(c.SCHEMA_V4, [P2])])
        self.assertIsNone(await c.read_route_item(db, self.ctx, str(P1), ('name',)))
        no_row = MagicMock()
        no_row.first.return_value = None
        db2 = self.db(scalars=[policy(c.SCHEMA_V4, [P1])], result=no_row)
        self.assertIsNone(await c.read_route_item(db2, self.ctx, str(P1), ('name',)))

    async def test_malformed_identity_and_fields_fail_closed(self):
        db = self.db()
        with self.assertRaises(SourceUnavailable):
            await c.read_route_item(db, self.ctx, 'not-a-uuid', ('name',))
        with self.assertRaises(SourceUnavailable):
            await c.read_route_item(db, self.ctx, str(P1), ('cost',))

    async def test_description_selected_only_after_explicit_optin(self):
        db = self.db(scalars=[policy(c.SCHEMA_V4, [P1])], result=first_row(P1, 'Screen'))
        item = await c.read_route_item(db, self.ctx, str(P1), ('description',))
        self.assertIsNone(item['description'])
        sql = str(db.execute.call_args[0][0])
        self.assertNotIn('description', sql)
        db2 = self.db(scalars=[policy(c.SCHEMA_V4, [P1], show_description=True)],
                      result=first_row(P1, 'Screen', 'Long text'))
        item2 = await c.read_route_item(db2, self.ctx, str(P1), ('description',))
        self.assertEqual(item2['description'], 'Long text')
        self.assertIn('description', str(db2.execute.call_args[0][0]))


class RouteBindingResolveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_route_binding_validates_and_resolves_from_context_route_item(self):
        ctx = SourceContext(A, 'en', frozenset({'inventory'}), route_item=str(P1))
        items = ScopedItems(AsyncMock())
        items.validate(ctx, route_binding('name'), 'text')
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=policy(c.SCHEMA_V4, [P1]))
        db.execute = AsyncMock(return_value=first_row(P1, 'Screen'))
        value = await ScopedItems(db).resolve(ctx, route_binding('name'), 'text')
        self.assertEqual(value, 'Screen')

    async def test_route_binding_hides_without_a_route_item(self):
        ctx = SourceContext(A, 'en', frozenset({'inventory'}))
        db = AsyncMock()
        self.assertIsNone(await ScopedItems(db).resolve(ctx, route_binding('name'), 'text'))
        db.scalar.assert_not_called()

    async def test_route_binding_validate_rejects_foreign_sources(self):
        ctx = SourceContext(A, 'en', frozenset({'inventory'}), route_item=str(P1))
        with self.assertRaises(SourceUnavailable):
            ScopedItems(AsyncMock()).validate(ctx, route_binding('cost'), 'text')
        with self.assertRaises(SourceUnavailable):
            ScopedItems(AsyncMock()).validate(ctx, {**route_binding('name'), 'module': 'billing'}, 'text')


class CategoryProductsProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    async def test_empty_without_route_item(self):
        db = AsyncMock()
        provider = p.category_products_provider(db)
        self.assertEqual(await provider.read(SourceContext(A, 'en', frozenset({'inventory'})), 5), [])
        db.scalar.assert_not_called()

    async def test_route_category_delegates_to_the_v4_gate(self):
        db = AsyncMock()
        db.scalar = AsyncMock(side_effect=[policy(c.SCHEMA_V4, [P1]), publication([CAT])])
        db.execute = AsyncMock(return_value=all_rows((P1, 'Screen')))
        provider = p.category_products_provider(db)
        ctx = SourceContext(A, 'en', frozenset({'inventory'}), route_item=str(CAT))
        rows = await provider.read(ctx, 5)
        self.assertEqual(rows, [{'item_key': str(P1), 'name': 'Screen', 'price': None, 'image': None}])

    async def test_contract_shape_is_valid_and_bounded(self):
        from app.framework.storefront_collections import collection_problems
        self.assertEqual(collection_problems(p._CATEGORY_PRODUCTS_CONTRACT), [])


class RouteEnvelopeShapeTests(unittest.TestCase):
    def test_v2_item_envelope_and_description_field(self):
        ok = {'schema': manifest.PAGE_BINDINGS_ROUTE_SCHEMA,
              'content': {'en': {'html': route_binding('description')}}}
        self.assertEqual(manifest.page_binding_problems(ok, 'text'), [])
        self.assertNotEqual(manifest.page_binding_problems(ok, 'heading'), [])
        pinned = {'schema': manifest.PAGE_BINDINGS_ROUTE_SCHEMA,
                  'content': {'en': {'text': {**route_binding('name'), 'item_key': str(P1)}}}}
        self.assertNotEqual(manifest.page_binding_problems(pinned, 'heading'), [])

    def test_v2_category_repeat_declaration(self):
        ok = {'schema': manifest.PAGE_REPEAT_CATEGORY_SCHEMA, 'slots': {'heading': 'name'},
              'content': {'en': {'module': 'inventory', 'source': 'category_products',
                                 'category': 'route', 'limit': 12, 'on_missing': 'hide'}}}
        self.assertEqual(manifest.page_repeat_problems(ok, 'column'), [])
        bad = {'schema': manifest.PAGE_REPEAT_CATEGORY_SCHEMA, 'slots': {'heading': 'name'},
               'content': {'en': {'module': 'inventory', 'source': 'category_products',
                                  'category': str(CAT), 'limit': 12, 'on_missing': 'hide'}}}
        self.assertNotEqual(manifest.page_repeat_problems(bad, 'column'), [])

    def test_route_item_context_requires_a_uuid(self):
        SourceContext(A, 'en', frozenset({'inventory'}), route_item=str(P1))
        with self.assertRaises(SourceUnavailable):
            SourceContext(A, 'en', frozenset({'inventory'}), route_item='../../etc')


if __name__ == '__main__':
    unittest.main()
