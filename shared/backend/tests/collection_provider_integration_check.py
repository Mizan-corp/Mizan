"""Real-model integration checks for collection provider consent gating.

Runs under Python 3.11+ with actual inventory/file models and real SQLAlchemy
statements (complements the 3.10-safe stub harness in
test_collection_typed_fields.py). Covers v0/v1 consent versions, column
selection before/after opt-in, provenance fail-closed, revocation and
cross-tenant refusal.
"""
import os, sys, json, unittest
from pathlib import Path
from uuid import UUID
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY', 'offline-test-not-used-for-signing')
os.environ['VERCEL'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.registry import load_all_models
load_all_models()
from app.activities.general.modules.inventory.storefront import cards, provider
from app.framework.storefront_collections import CollectionRuntime
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.platform.tenancy.context import current_tenant_id

A = UUID('00000000-0000-4000-8000-000000000001')
B = UUID('00000000-0000-4000-8000-000000000002')
P = UUID('00000000-0000-4000-8000-000000000003')
IMG = 'https://abc123.public.blob.vercel-storage.com/t/%s/product_image/%s/p.png' % (A, P)


def catalog():
    return json.dumps({'schema': provider.SCHEMA, 'products': [str(P)], 'categories': []})


def policy(schema, **patch):
    return json.dumps({'schema': schema, 'products': [str(P)], 'show_price': True,
                       'show_image': True, 'currency': 'EGP', **patch})


class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = current_tenant_id.set(A)
        self.ctx = SourceContext(A, 'en', frozenset({'inventory'}))
        self.db = AsyncMock()
        self.products = provider.inventory_providers(self.db)[0]

    async def asyncTearDown(self):
        current_tenant_id.reset(self.t)

    def _scalars(self, *values):
        self.db.scalar = AsyncMock(side_effect=list(values))

    def _rows(self, *tuples):
        r = MagicMock()
        r.all.return_value = list(tuples)
        self.db.execute.return_value = r

    def _sql(self):
        return str(self.db.execute.call_args.args[0])

    async def test_v0_policy_never_selects_optional_columns(self):
        self._scalars(catalog(), policy(cards.SCHEMA))
        self._rows((P, 'Widget'))
        rows = await self.products.read(self.ctx, 3)
        self.assertEqual(rows, [{'item_key': str(P), 'name': 'Widget', 'price': None, 'image': None}])
        sql = self._sql()
        self.assertIn('products.tenant_id', sql)
        self.assertIn('products.is_active IS true', sql)
        for field in ['retail_price', 'cost_price', 'wholesale_price', 'image_url', 'shelf_number', 'barcode']:
            self.assertNotIn(field, sql)

    async def test_v1_policy_selects_only_retail_price_and_image(self):
        self._scalars(catalog(), policy(cards.SCHEMA_V1), P)
        self._rows((P, 'Widget', Decimal('10.00'), IMG))
        rows = await self.products.read(self.ctx, 3)
        self.assertEqual(rows[0]['price'],
                         {'schema': 'mizan.money.experimental.v0', 'amount': '10.00', 'currency': 'EGP'})
        self.assertEqual(rows[0]['image'],
                         {'schema': 'mizan.media.experimental.v0', 'src': IMG, 'alt': 'Widget'})
        sql = self._sql()
        self.assertIn('retail_price', sql)
        self.assertIn('image_url', sql)
        for field in ['cost_price', 'wholesale_price', 'shelf_number', 'barcode']:
            self.assertNotIn(field, sql)
        # Provenance lookup is the same WorkspaceFile discipline as cards.
        provenance = str(self.db.scalar.call_args.args[0])
        self.assertIn('workspace_files.tenant_id', provenance)
        self.assertIn('workspace_files.owner_id', provenance)

    async def test_v1_image_without_provenance_fails_closed(self):
        self._scalars(catalog(), policy(cards.SCHEMA_V1), None)
        self._rows((P, 'Widget', Decimal('10.00'), IMG))
        with self.assertRaises(SourceUnavailable):
            await self.products.read(self.ctx, 3)

    async def test_v1_price_only_consent_skips_image_column(self):
        self._scalars(catalog(), policy(cards.SCHEMA_V1, show_image=False))
        self._rows((P, 'Widget', Decimal('10.00')))
        rows = await self.products.read(self.ctx, 3)
        self.assertEqual(rows[0]['price']['amount'], '10.00')
        self.assertIsNone(rows[0]['image'])
        self.assertNotIn('image_url', self._sql())

    async def test_revocation_by_v0_resave_drops_values_and_columns(self):
        # Re-saving under old v0 wording replaces the v1 row: list consent gone.
        self._scalars(catalog(), policy(cards.SCHEMA))
        self._rows((P, 'Widget'))
        rows = await self.products.read(self.ctx, 3)
        self.assertEqual(rows, [{'item_key': str(P), 'name': 'Widget', 'price': None, 'image': None}])
        self.assertNotIn('retail_price', self._sql())

    async def test_cross_tenant_and_module_refusal_before_any_read(self):
        for ctx in [SourceContext(B, 'en', frozenset({'inventory'})),
                    SourceContext(A, 'en', frozenset())]:
            with self.assertRaises(SourceUnavailable):
                await self.products.read(ctx, 3)
        self.db.scalar.assert_not_awaited()
        self.db.execute.assert_not_awaited()

    async def test_end_to_end_through_collection_runtime(self):
        self._scalars(catalog(), policy(cards.SCHEMA_V1), P)
        self._rows((P, 'Widget', Decimal('10.00'), IMG))
        runtime = CollectionRuntime(provider.inventory_providers(self.db))
        items = await runtime.items(self.ctx, 'inventory', 'products', 3)
        self.assertEqual(items[0].values['price']['currency'], 'EGP')
        self.assertEqual(items[0].values['image']['alt'], 'Widget')

    def test_stored_policy_accepts_all_versions_rejects_unknown(self):
        for schema in (cards.SCHEMA, cards.SCHEMA_V1, cards.SCHEMA_V2):
            self.assertEqual(cards.stored_policy(policy(schema))['products'], (P,))
        with self.assertRaises(SourceUnavailable):
            cards.stored_policy(policy('mizan.inventory-website-cards.experimental.v3'))
        with self.assertRaises(SourceUnavailable):
            cards.stored_policy('not json')
        self.assertEqual(cards.stored_policy(None),
                         {'products': (), 'show_price': False, 'show_image': False, 'currency': None})


if __name__ == '__main__':
    unittest.main()
