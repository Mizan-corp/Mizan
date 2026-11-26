"""v1 bounded card repeat: column template with heading/text/image slots filled
from typed collection fields (name text, display money, provenance media).

v0 heading repeats are unchanged (covered by test_collection_repeats); these
tests pin the new declaration shape, slot/type compatibility, expansion
semantics (hide/empty, derived identities, escaping) and renderer output.
"""
import importlib.util
import sys
import unittest

from test_collection_repeats import p, manifest, collections, r, A, ROOT

if 'app.framework.storefront_values' not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        'app.framework.storefront_values', ROOT / 'app/framework/storefront_values.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

IMG = 'https://abc123.public.blob.vercel-storage.com/t/%s/product_image/p1/p.png' % A
SLOTS = {'heading': 'name', 'text': 'price', 'image': 'image'}


def contract(name_nullable=False):
    return {'schema': collections.SCHEMA, 'module': 'inventory', 'source': 'products',
            'key': 'item_key',
            'fields': {'name': {'type': 'text', 'semantic': 'plain_text', 'nullable': name_nullable, 'max_length': 200},
                       'price': {'type': 'money', 'semantic': 'display_money', 'nullable': True},
                       'image': {'type': 'media', 'semantic': 'display_media', 'nullable': True}},
            'max_items': 24}


def card_tree(slots=SLOTS, on_missing='hide'):
    children = []
    if 'heading' in slots:
        children.append({'id': 'n_chd00', 'type': 'heading', 'settings': {},
                         'content': {'en': {'text': 'Name'}, 'ar': {'text': 'اسم'}}})
    if 'text' in slots:
        children.append({'id': 'n_ctxt0', 'type': 'text', 'settings': {},
                         'content': {'en': {'html': '<p>price</p>'}}})
    if 'image' in slots:
        children.append({'id': 'n_cimg0', 'type': 'image', 'settings': {},
                         'content': {'en': {'src': 'https://example.com/x.png', 'alt': 'x'}}})
    column = {'id': 'n_ccol0', 'type': 'column', 'settings': {}, 'content': {}, 'children': children,
              'repeat': {'schema': manifest.PAGE_REPEAT_CARD_SCHEMA, 'slots': slots,
                         'content': {'en': {'module': 'inventory', 'source': 'products',
                                            'limit': 3, 'on_missing': on_missing}}}}
    return {'id': 'n_root0', 'type': 'section', 'settings': {}, 'content': {},
            'children': [{'id': 'n_row00', 'type': 'columns', 'settings': {}, 'content': {},
                          'children': [column]}]}


def rows(*items):
    async def read(context, limit):
        return [dict(item) for item in items]
    return collections.CollectionRuntime((collections.CollectionProvider(contract(), read),))


def item(key, name, price='10.00', img=IMG):
    return {'item_key': key, 'name': name,
            'price': None if price is None else {'schema': 'mizan.money.experimental.v0', 'amount': price, 'currency': 'EGP'},
            'image': None if img is None else {'schema': 'mizan.media.experimental.v0', 'src': img, 'alt': name}}


def columns_of(out):
    # section > columns row > expanded card columns
    return out['children'][0]['children']


class ManifestTests(unittest.TestCase):
    def test_valid_v1_declaration_passes(self):
        self.assertEqual(manifest.page_problems(card_tree()), [])

    def test_v1_rejected_on_heading_and_without_heading_slot(self):
        t = card_tree()
        repeat = t['children'][0]['children'][0].pop('repeat')
        t['children'][0]['children'][0] = {
            'id': 'n_chd00', 'type': 'heading', 'settings': {}, 'content': {'en': {'text': 'x'}}, 'repeat': repeat}
        self.assertTrue(manifest.page_problems(t))
        t = card_tree(slots={'text': 'price'})
        self.assertTrue(manifest.page_problems(t))

    def test_unknown_slot_key_and_bad_plan_rejected(self):
        t = card_tree()
        t['children'][0]['children'][0]['repeat']['slots'] = {'heading': 'name', 'gallery': 'image'}
        self.assertTrue(manifest.page_problems(t))
        t = card_tree()
        t['children'][0]['children'][0]['repeat']['content']['en']['field'] = 'name'
        self.assertTrue(manifest.page_problems(t))


class ExpansionTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_filters_cards_case_insensitively(self):
        runtime = rows(item('p1', 'Laptop HP'), item('p2', 'Monitor LG'), item('p3', 'laptop bag'))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        out = await p.resolve_repeat(card_tree(), runtime, ctx, query='LAPTOP')
        self.assertEqual([c['children'][0]['content']['en']['text'] for c in columns_of(out)],
                         ['Laptop HP', 'laptop bag'])

    async def test_query_none_or_blank_keeps_everything(self):
        runtime = rows(item('p1', 'Widget'), item('p2', 'Gadget'))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        for q in (None, '', '   '):
            out = await p.resolve_repeat(card_tree(), runtime, ctx, query=q)
            self.assertEqual(len(columns_of(out)), 2)

    async def test_query_without_matches_shows_empty_state(self):
        runtime = rows(item('p1', 'Widget'))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        out = await p.resolve_repeat(card_tree(), runtime, ctx, query='zzz')
        cards = columns_of(out)
        self.assertEqual(len(cards), 1)
        node = cards[0]['children'][0]
        self.assertEqual(node['type'], 'text')
        self.assertIn('zzz', node['content']['en']['html'])
        self.assertIn('zzz', node['content']['ar']['html'])
        self.assertEqual(manifest.page_problems(out, ('en', 'ar')), [])

    async def test_query_never_matches_text_outside_the_disclosed_heading_field(self):
        # Consent contract (2026-11-26): filtering sees only the disclosed
        # heading text, through the same consent-checked reader the render
        # uses. A needle that exists only in a record attribute the collection
        # does not disclose (a description, say) must not match, count or
        # rank. The runtime pins this two ways: items() rejects provider rows
        # carrying keys outside the reviewed contract, and text() reads only
        # the contracted heading field.
        sneaky = dict(item('p2', 'Plain Box'))
        sneaky['description'] = 'codeword'
        runtime = rows(item('p1', 'Laptop HP'), sneaky)
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        with self.assertRaises(collections.ProjectionInvalid):
            await p.resolve_repeat(card_tree(), runtime, ctx, query='codeword')

    async def test_query_cannot_target_an_undeclared_field(self):
        # Asking the reader for a field outside the contract (e.g. a hidden
        # description) fails closed instead of searching it.
        runtime = rows(item('p1', 'Widget'))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        items = await runtime.items(ctx, 'inventory', 'products', 3)
        with self.assertRaises(r.SourceUnavailable):
            runtime.text(ctx, items[0], module='inventory', source='products',
                         field='description', on_missing='hide')

    async def test_queryless_all_hidden_still_prunes_row(self):
        async def read(context, limit):
            return [dict(item('p1', None, img=None))]
        runtime = collections.CollectionRuntime(
            (collections.CollectionProvider(contract(name_nullable=True), read),))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        out = await p.resolve_repeat(card_tree(), runtime, ctx)
        self.assertEqual(out['children'], [])

    async def test_expands_typed_slots_with_stable_identities(self):
        runtime = rows(item('p1', 'Widget'), item('p2', 'Gadget', price='25.50'))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        source = card_tree()
        out = await p.resolve_repeat(source, runtime, ctx)
        cards = columns_of(out)
        self.assertEqual(len(cards), 2)
        self.assertEqual([c['children'][0]['content']['en']['text'] for c in cards], ['Widget', 'Gadget'])
        self.assertEqual(cards[0]['children'][1]['content']['en']['html'], '<p>10.00 EGP</p>')
        self.assertEqual(cards[1]['children'][1]['content']['en']['html'], '<p>25.50 EGP</p>')
        self.assertEqual(cards[0]['children'][2]['content']['en']['src'], IMG)
        self.assertEqual(cards[0]['children'][2]['content']['en']['alt'], 'Widget')
        self.assertEqual(manifest.page_problems(out), [])
        self.assertIn('repeat', source['children'][0]['children'][0])  # source unmutated
        ids = [n['id'] for c in cards for n in [c, *c['children']]]
        self.assertEqual(len(ids), len(set(ids)))
        again = columns_of(await p.resolve_repeat(card_tree(), runtime, ctx))
        self.assertEqual([c['id'] for c in again], [c['id'] for c in cards])  # stable across renders

    async def test_more_than_six_cards_split_into_valid_rows(self):
        """A columns row holds 1..6 columns; 8 items must render as two valid
        sibling rows (6+2), never one over-full invalid row (live Phase 3 503)."""
        runtime = rows(*[item('p%d' % i, 'Item %d' % i) for i in range(8)])
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        tree = card_tree()
        tree['children'][0]['children'][0]['repeat']['content']['en']['limit'] = 8
        out = await p.resolve_repeat(tree, runtime, ctx)
        self.assertEqual(manifest.page_problems(out), [])
        rows_out = out['children']
        self.assertEqual([len(row['children']) for row in rows_out], [6, 2])
        names = [c['children'][0]['content']['en']['text'] for row in rows_out for c in row['children']]
        self.assertEqual(names, ['Item %d' % i for i in range(8)])
        ids = [row['id'] for row in rows_out] + [n['id'] for row in rows_out for c in row['children'] for n in [c, *c['children']]]
        self.assertEqual(len(ids), len(set(ids)))

    async def test_split_rows_honor_declared_track_count(self):
        """A row declaring 4 tracks splits 8 items 4+4 (uniform rows whose own
        grid gap applies within each), never 6+2 with an orphan pair."""
        runtime = rows(*[item('p%d' % i, 'Item %d' % i) for i in range(8)])
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        tree = card_tree()
        tree['children'][0]['settings'] = {'desktop': {'columns': 4}}
        tree['children'][0]['children'][0]['repeat']['content']['en']['limit'] = 8
        out = await p.resolve_repeat(tree, runtime, ctx)
        self.assertEqual(manifest.page_problems(out), [])
        rows_out = out['children']
        self.assertEqual([len(row['children']) for row in rows_out], [4, 4])
        # Every cloned row keeps the declared track count.
        self.assertTrue(all(row['settings']['desktop']['columns'] == 4 for row in rows_out))

    async def test_route_category_plan_expands_through_route_context(self):
        """Phase 3 route-parameterized read: a v2 category plan with
        category='route' resolves through the request's route_item context."""
        runtime = rows(item('p1', 'Dessert'), item('p2', 'Gateau'))
        ctx = r.SourceContext(A, 'ar', frozenset({'inventory'}), route_item='3d184be9-0c9e-4c1f-8a7f-e7f5cbfb7a64')
        tree = card_tree()
        repeat = tree['children'][0]['children'][0]['repeat']
        repeat['schema'] = manifest.PAGE_REPEAT_CATEGORY_SCHEMA
        repeat['content'] = {'ar': {'module': 'inventory', 'source': 'products', 'category': 'route',
                                    'limit': 3, 'on_missing': 'hide'}}
        out = await p.resolve_repeat(tree, runtime, ctx)
        self.assertEqual(manifest.page_problems(out), [])
        cards = columns_of(out)
        self.assertEqual([c['children'][0]['content']['ar']['text'] for c in cards], ['Dessert', 'Gateau'])

    async def test_hide_and_empty_missing_semantics(self):
        runtime = rows(item('p1', 'NoPrice', price=None, img=None))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        out = await p.resolve_repeat(card_tree(on_missing='hide'), runtime, ctx)
        kinds = [c['type'] for c in columns_of(out)[0]['children']]
        self.assertEqual(kinds, ['heading'])  # null price/image children dropped, card kept
        out = await p.resolve_repeat(card_tree(on_missing='empty'), runtime, ctx)
        kinds = [c['type'] for c in columns_of(out)[0]['children']]
        self.assertEqual(kinds, ['heading', 'text'])  # empty price paragraph; image still dropped
        self.assertEqual(columns_of(out)[0]['children'][1]['content']['en']['html'], '<p></p>')

    async def test_heading_hide_skips_card(self):
        c = contract(name_nullable=True)
        async def read(context, limit):
            return [{'item_key': 'p1', 'name': None, 'price': None, 'image': None}]
        runtime = collections.CollectionRuntime((collections.CollectionProvider(c, read),))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        out = await p.resolve_repeat(card_tree(), runtime, ctx)
        def columns_in(node):
            found = [n for n in node.get('children', []) if n['type'] == 'column']
            for child in node.get('children', []):
                found.extend(columns_in(child))
            return found
        self.assertEqual(columns_in(out), [])  # all-hidden items prune the whole row

    async def test_slot_type_compatibility_refused_before_read(self):
        async def read(*_):
            raise AssertionError('must not read')
        runtime = collections.CollectionRuntime((collections.CollectionProvider(contract(), read),))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        for slots in [{'heading': 'price', 'text': 'price'}, {'heading': 'name', 'image': 'name'},
                      {'heading': 'name', 'image': 'price'}, {'heading': 'name', 'text': 'unknown'}]:
            t = card_tree(slots=slots)
            # Manifest shape passes (slot VALUES are opaque identifiers there);
            # runtime compatibility refuses.
            with self.assertRaises(r.SourceUnavailable):
                await p.resolve_repeat(t, runtime, ctx)

    async def test_bindings_mixed_with_card_repeat_refused(self):
        runtime = rows(item('p1', 'Widget'))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        t = card_tree()
        t['children'][0]['children'][0]['children'][0]['bindings'] = {'schema': 'x'}
        with self.assertRaises(r.SourceUnavailable):
            await p.resolve_repeat(t, runtime, ctx)

    async def test_inactive_language_plan_validated_before_read(self):
        async def read(*_):
            raise AssertionError('must not read')
        runtime = collections.CollectionRuntime((collections.CollectionProvider(contract(), read),))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        t = card_tree()
        t['children'][0]['children'][0]['repeat']['content']['ar'] = {
            'module': 'unknown', 'source': 'products', 'limit': 3, 'on_missing': 'hide'}
        with self.assertRaises(r.SourceUnavailable):
            await p.resolve_repeat(t, runtime, ctx)

    async def test_text_slot_value_is_escaped(self):
        runtime = rows(item('p1', '<script>bad()</script>'))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        # Name renders through the heading (plain text); also pin a text field.
        c = contract()
        c['fields']['note'] = c['fields'].pop('image')  # media spec under a text-slot reuse is wrong; rebuild
        c['fields']['note'] = {'type': 'text', 'semantic': 'plain_text', 'nullable': True, 'max_length': 200}
        async def read(context, limit):
            return [{'item_key': 'p1', 'name': 'Widget', 'price': None, 'note': '<script>bad()</script>'}]
        runtime = collections.CollectionRuntime((collections.CollectionProvider(c, read),))
        t = card_tree(slots={'heading': 'name', 'text': 'note'})
        out = await p.resolve_repeat(t, runtime, ctx)
        html = columns_of(out)[0]['children'][1]['content']['en']['html']
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    async def test_renderer_outputs_price_and_image(self):
        runtime = rows(item('p1', 'Widget'))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        out = await p.resolve_repeat(card_tree(), runtime, ctx)
        spec = importlib.util.spec_from_file_location('card_repeat_renderer', ROOT / 'app/platform/site/render.py')
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        page = renderer.render_page(out, lang='en')
        self.assertIn('10.00 EGP', page)
        self.assertIn(IMG, page)
        self.assertIn('Widget', page)


class TypedValueScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_typed_value_scope_and_text_refusal(self):
        runtime = rows(item('p1', 'Widget'))
        ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))
        items = await runtime.items(ctx, 'inventory', 'products', 3)
        with self.assertRaises(r.SourceUnavailable):
            runtime.typed_value(ctx, items[0], module='inventory', source='products', field='name')
        with self.assertRaises(r.SourceUnavailable):
            runtime.typed_value(r.SourceContext(A, 'ar', frozenset({'inventory'})), items[0],
                                module='inventory', source='products', field='price')
        value = runtime.typed_value(ctx, items[0], module='inventory', source='products', field='price')
        self.assertEqual(value['amount'], '10.00')
        media = runtime.typed_value(ctx, items[0], module='inventory', source='products', field='image')
        self.assertEqual(media['src'], IMG)


if __name__ == '__main__':
    unittest.main()
