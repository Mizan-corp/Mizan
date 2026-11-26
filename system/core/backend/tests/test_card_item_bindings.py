"""Card pages may also carry v1 individually-bound elements outside the card.

The pre-write bound-tree check and the render path used to drop the items
resolver on the card branch, so any page mixing a product card with an
individually bound image/text/heading was refused as 'binding source
unavailable'. These tests pin the resolver passing through card_plan and
resolve_cards, and the fail-closed behavior when it is absent.
"""
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import app.models.registry  # noqa: F401
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.platform.site.storefront import card_runtime

A = uuid.UUID('a1b975ac-32ac-4813-9b35-e43069616c5f')
CTX = SourceContext(A, 'en', frozenset({'inventory'}))

ITEM = {'mode': 'dynamic', 'module': 'inventory', 'source': 'products',
        'item_key': 'b2c075bd43bd5924a645d53079717d60', 'field': 'image', 'on_missing': 'hide'}


def tree():
    return {'id': 'n_root0', 'type': 'section', 'settings': {}, 'content': {}, 'children': [
        {'id': 'n_row00', 'type': 'columns', 'settings': {}, 'content': {}, 'children': [
            {'id': 'n_card00', 'type': 'column', 'settings': {}, 'content': {},
             'card': {'schema': 'mizan.page-card.experimental.v0',
                      'content': {'en': {'module': 'inventory', 'source': 'website_cards', 'limit': 1,
                                         'targets': {'name': 'n_name00', 'price': 'n_price0', 'image': 'n_cimg00'}}}},
             'children': [
                 {'id': 'n_name00', 'type': 'heading', 'settings': {'desktop': {'level': 3}}, 'content': {'en': {'text': 'Name'}}},
                 {'id': 'n_price0', 'type': 'text', 'settings': {}, 'content': {'en': {'html': '<p>0</p>'}}},
                 {'id': 'n_cimg00', 'type': 'image', 'settings': {}, 'content': {'en': {'src': 'https://example.com/a.png', 'alt': 'a'}}}]},
            ]},
        {'id': 'n_row01', 'type': 'columns', 'settings': {}, 'content': {}, 'children': [
            {'id': 'n_col000', 'type': 'column', 'settings': {}, 'content': {}, 'children': [
                {'id': 'n_bind00', 'type': 'image', 'settings': {},
                 'content': {'en': {'src': 'https://example.com/b.png', 'alt': 'b'}},
                 'bindings': {'schema': 'mizan.page-bindings.experimental.v1',
                              'content': {'en': {'src': dict(ITEM)}}}}]}]}]}


class FakeItems:
    def __init__(self):
        self.validated = []

    def validate(self, context, binding, field):
        self.validated.append((binding['item_key'], field))

    async def resolve(self, context, binding, field):
        return 'https://example.com/resolved.png'


class Tests(unittest.IsolatedAsyncioTestCase):
    def test_card_plan_validates_item_bindings_with_resolver(self):
        items = FakeItems()
        static, declarations, scalars = card_runtime.card_plan(tree(), MagicMock(), CTX, items)
        self.assertEqual(items.validated, [(ITEM['item_key'], 'src')])
        self.assertEqual(len(declarations), 1)
        self.assertEqual(scalars['n_bind00']['schema'], 'mizan.page-bindings.experimental.v1')

    def test_card_plan_without_resolver_still_fails_closed(self):
        with self.assertRaises(SourceUnavailable):
            card_runtime.card_plan(tree(), MagicMock(), CTX)

    async def test_resolve_cards_resolves_item_bindings(self):
        rows = [{'item_key': 'k', 'name': 'Card', 'price': None, 'image': None}]
        with patch.object(card_runtime, 'read_cards', new=AsyncMock(return_value=rows)), \
             patch.object(card_runtime, 'item_resolver', return_value=FakeItems()):
            out = await card_runtime.resolve_cards(AsyncMock(), tree(), CTX)

        def find(node, nid):
            if node['id'] == nid:
                return node
            for child in node.get('children', []):
                hit = find(child, nid)
                if hit is not None:
                    return hit
            return None

        bound = find(out, 'n_bind00')
        self.assertEqual(bound['content']['en']['src'], 'https://example.com/resolved.png')


if __name__ == '__main__':
    unittest.main()
