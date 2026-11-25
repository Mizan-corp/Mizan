"""Typed money/media collection fields: schema, projection and consent gating.

Prep slice for the collection provider extension. The v1 display consent that
would populate price/image cannot be written yet (consent-scope wording under
review), so live behavior is unchanged: typed-value tests inject a v1 policy
directly. A v0 (cards-worded) policy must yield no typed values.

Loads provider.py/cards.py against stubbed SQLAlchemy/model dependencies so it
runs offline on Python 3.10 (the real models require 3.11; the full-model
integration checks cover the real imports elsewhere).
"""
import importlib.util
import json
import pathlib
import sys
import types
import unittest
from contextvars import ContextVar
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from test_storefront_runtime import r, A, Z
from test_storefront_collections import m
from test_storefront_bindings import manifest, tree as bound_tree  # noqa: F401  registers app.framework.manifest

ROOT = pathlib.Path(__file__).resolve().parents[1]
P1 = UUID('b2c075bd-43bd-5924-a645-d53079717d60')
IMG = 'https://abc123.public.blob.vercel-storage.com/t/%s/product_image/%s/p.png' % (A, P1)


class FakeCol:
    def __init__(self, name):
        self.name = name
    def _expr(self, *args):
        return ('expr', self.name, args)
    def __eq__(self, other):
        return self._expr(other)
    def in_(self, values):
        return self._expr(values)
    def is_(self, value):
        return self._expr(value)


class FakeSelect:
    def __init__(self, *cols):
        self.columns = list(cols)
    def where(self, *conds):
        return self
    def order_by(self, *cols):
        return self
    def limit(self, n):
        return self


def stub_model(**cols):
    return type('StubModel', (), {name: FakeCol(name) for name in cols})


def load_real(name, relpath):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def package(name):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = []
        sys.modules[name] = mod
    return sys.modules[name]


values = load_real('app.framework.storefront_values', 'app/framework/storefront_values.py')

sqlalchemy = types.ModuleType('sqlalchemy')
sqlalchemy.select = lambda *cols: FakeSelect(*cols)

settings_models = types.ModuleType('app.platform.settings.models')
settings_models.StoreSetting = stub_model(tenant_id='tenant_id', key='key', value='value')

files_mod = types.ModuleType('app.framework.files')
files_mod.WorkspaceFile = stub_model(id='id', tenant_id='tenant_id', kind='kind',
                                     owner_id='owner_id', url='url', content_type='content_type')

tenancy = types.ModuleType('app.platform.tenancy.context')
tenancy.current_tenant_id = ContextVar('typed_fields_test_tenant', default=None)

Product = stub_model(id='id', name='name', tenant_id='tenant_id', is_active='is_active',
                     retail_price='retail_price', image_url='image_url')
Category = stub_model(id='id', name='name', tenant_id='tenant_id')
product_mod = types.ModuleType('app.activities.general.modules.inventory.models.product')
product_mod.Product = Product
product_mod.Category = Category

pkg = 'app.activities.general.modules.inventory.storefront'
for parent in ['app.platform', 'app.platform.settings', 'app.platform.tenancy',
               'app.activities', 'app.activities.general', 'app.activities.general.modules',
               'app.activities.general.modules.inventory',
               'app.activities.general.modules.inventory.models', pkg]:
    package(parent)

# Load cards/provider against the stubs, then restore sys.modules so the
# stubs (fake sqlalchemy above all) cannot leak into later test modules in a
# full discover run. The loaded modules bound their imports at load time;
# the only stubs still needed at call time stay registered below.
_HYGIENE = ['sqlalchemy', 'app.platform', 'app.platform.settings',
            'app.platform.settings.models', 'app.platform.tenancy',
            'app.platform.tenancy.context', 'app.activities',
            'app.activities.general', 'app.activities.general.modules',
            'app.activities.general.modules.inventory',
            'app.activities.general.modules.inventory.models',
            'app.activities.general.modules.inventory.models.product']
_saved = {k: sys.modules.get(k) for k in _HYGIENE}
sys.modules.update({
    'sqlalchemy': sqlalchemy,
    'app.platform.settings.models': settings_models,
    'app.framework.files': files_mod,
    'app.platform.tenancy.context': tenancy,
    'app.activities.general.modules.inventory.models.product': product_mod})
cards = load_real(pkg + '.cards', 'app/activities/general/modules/inventory/storefront/cards.py')
provider = load_real(pkg + '.provider', 'app/activities/general/modules/inventory/storefront/provider.py')
for _k, _v in _saved.items():
    if _v is None:
        sys.modules.pop(_k, None)
    else:
        sys.modules[_k] = _v
# Runtime lazy imports still resolve: provider.read does `from .cards import
# display_consent` (pkg + pkg.cards stay registered) and `from
# app.framework.files import WorkspaceFile` (stub kept; the real module is not
# importable in the offline harness anyway).

projection = load_real('collection_projection_typed_test',
                       'app/platform/site/storefront/collection_projection.py')

def heading_tree():
    t = bound_tree()
    leaf = t['children'][0]['children'][0]['children'][0]
    leaf.pop('bindings')
    return t


def v1_policy(show_price=True, show_image=True, products=(P1,), currency='EGP'):
    return json.dumps({'schema': cards.SCHEMA_V1, 'products': [str(p) for p in products],
                       'show_price': show_price, 'show_image': show_image,
                       'currency': currency if show_price else None})


def catalog_selection():
    return json.dumps({'schema': provider.SCHEMA, 'products': [str(P1)], 'categories': []})


class ContractSchemaTests(unittest.TestCase):
    def test_typed_money_media_specs_accepted(self):
        c = provider.text_contract('products')
        self.assertEqual(m.collection_problems(c), [])
        self.assertEqual(c['fields']['price']['type'], 'money')
        self.assertEqual(c['fields']['image']['type'], 'media')

    def test_categories_contract_stays_name_only(self):
        c = provider.text_contract('categories')
        self.assertEqual(set(c['fields']), {'name'})
        self.assertEqual(m.collection_problems(c), [])

    def test_typed_spec_with_max_length_rejected(self):
        c = provider.text_contract('products')
        c['fields']['price']['max_length'] = 10
        self.assertIn('field: typed fields use the exact bounded declaration', m.collection_problems(c))

    def test_typed_spec_wrong_semantic_rejected(self):
        c = provider.text_contract('products')
        c['fields']['price']['semantic'] = 'plain_text'
        self.assertIn('field: typed fields use the exact bounded declaration', m.collection_problems(c))


class HeadingPlanTests(unittest.TestCase):
    def setUp(self):
        self.runtime = m.CollectionRuntime(provider.inventory_providers(AsyncMock()))
        self.ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))

    def test_typed_field_refused_for_heading_expansion(self):
        plan = {'template_id': 'n_heading', 'module': 'inventory', 'source': 'products',
                'field': 'price', 'limit': 3, 'on_missing': 'hide'}
        with self.assertRaises(r.SourceUnavailable) as cm:
            projection.checked_template(heading_tree(), plan, self.runtime, self.ctx)
        self.assertIn('plain text', str(cm.exception))

    def test_text_field_still_accepted(self):
        plan = {'template_id': 'n_heading', 'module': 'inventory', 'source': 'products',
                'field': 'name', 'limit': 3, 'on_missing': 'hide'}
        projection.checked_template(heading_tree(), plan, self.runtime, self.ctx)


class RuntimeValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_items_validates_money_and_media_values(self):
        async def read(context, limit):
            return [{'item_key': str(P1), 'name': 'Widget',
                     'price': {'schema': 'mizan.money.experimental.v0', 'amount': '10.00', 'currency': 'EGP'},
                     'image': {'schema': 'mizan.media.experimental.v0', 'src': IMG, 'alt': 'Widget'}}]
        runtime = m.CollectionRuntime((m.CollectionProvider(provider.text_contract('products'), read),))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        items = await runtime.items(ctx, 'inventory', 'products', 3)
        self.assertEqual(items[0].values['price']['amount'], '10.00')

    async def test_items_rejects_bad_money_value(self):
        async def read(context, limit):
            return [{'item_key': str(P1), 'name': 'Widget',
                     'price': {'schema': 'mizan.money.experimental.v0', 'amount': '10.0', 'currency': 'EGP'},
                     'image': None}]
        runtime = m.CollectionRuntime((m.CollectionProvider(provider.text_contract('products'), read),))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        with self.assertRaises(r.ProjectionInvalid):
            await runtime.items(ctx, 'inventory', 'products', 3)


class ProviderConsentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t = tenancy.current_tenant_id.set(A)
        self.ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        self.db = AsyncMock()
        self.products = provider.inventory_providers(self.db)[0]

    async def asyncTearDown(self):
        tenancy.current_tenant_id.reset(self.t)

    def _scalars(self, catalog_raw, consent_raw, workspace_file=True):
        # scalar() order: catalog selection, then display consent, then (when
        # an image url is opted in) the WorkspaceFile provenance lookup.
        values = [catalog_raw, consent_raw, P1 if workspace_file else None]
        self.db.scalar = AsyncMock(side_effect=values)

    def _rows(self, *tuples):
        result = MagicMock()
        result.all.return_value = list(tuples)
        self.db.execute.return_value = result

    async def test_v0_consent_yields_no_typed_values(self):
        self._scalars(catalog_selection(), v1_policy().replace(cards.SCHEMA_V1, cards.SCHEMA))
        self._rows((P1, 'Widget'))
        rows = await self.products.read(self.ctx, 3)
        self.assertEqual(rows, [{'item_key': str(P1), 'name': 'Widget', 'price': None, 'image': None}])
        # No v1 opt-in: optional columns were not even selected.
        self.assertEqual(len(self.db.execute.call_args.args[0].columns), 2)

    async def test_v1_consent_fills_typed_values_with_provenance(self):
        self._scalars(catalog_selection(), v1_policy())
        self._rows((P1, 'Widget', Decimal('10.00'), IMG))
        rows = await self.products.read(self.ctx, 3)
        self.assertEqual(rows[0]['price'],
                         {'schema': 'mizan.money.experimental.v0', 'amount': '10.00', 'currency': 'EGP'})
        self.assertEqual(rows[0]['image'],
                         {'schema': 'mizan.media.experimental.v0', 'src': IMG, 'alt': 'Widget'})
        self.assertEqual(len(self.db.execute.call_args.args[0].columns), 4)

    async def test_v1_image_without_provenance_fails_closed(self):
        self._scalars(catalog_selection(), v1_policy(), workspace_file=False)
        self._rows((P1, 'Widget', Decimal('10.00'), IMG))
        with self.assertRaises(r.SourceUnavailable):
            await self.products.read(self.ctx, 3)

    async def test_v1_product_not_in_consent_gets_no_typed_values(self):
        self._scalars(catalog_selection(), v1_policy(products=(Z,)))
        self._rows((P1, 'Widget', Decimal('10.00'), IMG))
        rows = await self.products.read(self.ctx, 3)
        self.assertIsNone(rows[0]['price'])
        self.assertIsNone(rows[0]['image'])

    async def test_no_consent_means_no_typed_values(self):
        self._scalars(catalog_selection(), None)
        self._rows((P1, 'Widget'))
        rows = await self.products.read(self.ctx, 3)
        self.assertEqual(rows, [{'item_key': str(P1), 'name': 'Widget', 'price': None, 'image': None}])

    async def test_revocation_via_v0_rewrite_drops_typed_values(self):
        # Owner re-saving under the existing v0 card wording revokes list
        # display consent: the v1 policy is gone, values return to None.
        self._scalars(catalog_selection(),
                      json.dumps({'schema': cards.SCHEMA, 'products': [str(P1)],
                                  'show_price': True, 'show_image': True, 'currency': 'EGP'}))
        self._rows((P1, 'Widget'))
        rows = await self.products.read(self.ctx, 3)
        self.assertEqual(rows, [{'item_key': str(P1), 'name': 'Widget', 'price': None, 'image': None}])

    async def test_cross_tenant_context_refused(self):
        ctx = r.SourceContext(Z, 'en', frozenset({'inventory'}))
        with self.assertRaises(r.SourceUnavailable):
            await self.products.read(ctx, 3)
        self.db.scalar.assert_not_awaited()

    async def test_rows_pass_collection_runtime_end_to_end(self):
        self._scalars(catalog_selection(), v1_policy())
        self._rows((P1, 'Widget', Decimal('10.00'), IMG))
        runtime = m.CollectionRuntime(provider.inventory_providers(self.db))
        items = await runtime.items(self.ctx, 'inventory', 'products', 3)
        self.assertEqual(items[0].values['price']['currency'], 'EGP')
        self.assertEqual(items[0].values['image']['alt'], 'Widget')


if __name__ == '__main__':
    unittest.main()
