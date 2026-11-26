"""Scalar-binding gate: an inventory collection contract cannot be laundered
into the scalar binding registry, and an inventory scalar binding is refused
while no scoped-item contract and no consent wording cover individual element
binding. The v1 display consent names product cards and repeating lists only;
this pins the refusal until the consent-scope wording change ships.
"""
import unittest

from test_storefront_runtime import r, CONTRACT, T, A
from test_collection_repeats import collections


def collection_contract():
    return {'schema': collections.SCHEMA, 'module': 'inventory', 'source': 'products',
            'key': 'item_key',
            'fields': {'name': {'type': 'text', 'semantic': 'plain_text', 'nullable': False, 'max_length': 200},
                       'price': {'type': 'money', 'semantic': 'display_money', 'nullable': True},
                       'image': {'type': 'media', 'semantic': 'display_media', 'nullable': True}},
            'max_items': 24}


BINDING = {'mode': 'dynamic', 'module': 'inventory', 'source': 'products',
           'field': 'name', 'on_missing': 'hide'}


class ScalarBindingGateTests(unittest.IsolatedAsyncioTestCase):
    def test_collection_contract_cannot_register_as_scalar_provider(self):
        async def read(*_):
            return None
        with self.assertRaises(ValueError):
            r.ProviderRegistry((r.Provider('inventory', collection_contract(), read, False),))

    def test_inventory_scalar_binding_refused_without_registered_module(self):
        async def read(*_):
            return None
        reg = r.ProviderRegistry((r.Provider('site', CONTRACT, read, True),))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        with self.assertRaises(r.SourceUnavailable):
            reg.validate_binding(ctx, BINDING, T)

    async def test_inventory_scalar_resolve_never_calls_provider(self):
        called = []

        async def read(*_):
            called.append(1)
            return None
        reg = r.ProviderRegistry((r.Provider('site', CONTRACT, read, True),))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        with self.assertRaises(r.SourceUnavailable):
            await reg.resolve(ctx, BINDING, T)
        self.assertEqual(called, [])

    def test_typed_price_image_scalar_targets_refused(self):
        async def read(*_):
            return None
        reg = r.ProviderRegistry((r.Provider('site', CONTRACT, read, True),))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        for field, target in [('price', {'type': 'money', 'semantic': 'display_money', 'cardinality': 'one', 'element': 'text'}),
                              ('image', {'type': 'media', 'semantic': 'display_media', 'cardinality': 'one', 'element': 'image'})]:
            with self.assertRaises(r.SourceUnavailable):
                reg.validate_binding(ctx, {**BINDING, 'field': field}, target)


if __name__ == '__main__':
    unittest.main()
