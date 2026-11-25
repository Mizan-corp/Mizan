"""Experimental v1 individually-bound elements: envelope shape, fail-closed
wiring, pre-read validation order, and renderer-safe fills. A fake items
resolver stands in for the consent-checked record read; the consent gate
itself is covered by test_scoped_item_consent.py with real models/statements.
"""
import copy
import importlib.util
import pathlib
import sys
import unittest
from test_storefront_runtime import r, CONTRACT, B, A

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_manifest', ROOT / 'app/framework/manifest.py')
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
sys.modules['app.framework.manifest'] = manifest

spec = importlib.util.spec_from_file_location('bindings', ROOT / 'app/platform/site/storefront/bindings.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

spec = importlib.util.spec_from_file_location('item_bindings', ROOT / 'app/platform/site/storefront/item_bindings.py')
im = importlib.util.module_from_spec(spec)
spec.loader.exec_module(im)

ITEM = {'mode': 'dynamic', 'module': 'inventory', 'source': 'products',
        'item_key': 'b2c075bd-43bd-5924-a645-d53079717d60', 'field': 'name', 'on_missing': 'hide'}


def item_tree(ntype='heading', field='text', binding=None, static=None):
    leaf = {'id': 'n_leaf00', 'type': ntype, 'settings': {}, 'content': {'en': static or {field: 'static fallback'}},
            'bindings': {'schema': manifest.PAGE_BINDINGS_ITEM_SCHEMA,
                         'content': {'en': {field: dict(binding or ITEM)}}}}
    return {'id': 'n_root0', 'type': 'section', 'settings': {}, 'content': {}, 'children': [
        {'id': 'n_row00', 'type': 'columns', 'settings': {}, 'content': {}, 'children': [
            {'id': 'n_col00', 'type': 'column', 'settings': {}, 'content': {}, 'children': [leaf]}]}]}


def validate(t):
    return manifest.page_problems(t)


def out_leaf(out):
    return out['children'][0]['children'][0]['children'][0]


class FakeItems:
    def __init__(self, value='Resolved name', fail_validate=False):
        self.value = value
        self.fail_validate = fail_validate
        self.validated = []
        self.resolved = []

    def validate(self, context, binding, field):
        self.validated.append((binding['item_key'], field))
        if self.fail_validate:
            raise r.SourceUnavailable('refused')

    async def resolve(self, context, binding, field):
        self.resolved.append((binding['item_key'], field))
        return self.value


class ManifestShapeTests(unittest.TestCase):
    def test_valid_v1_envelopes_accepted(self):
        for ntype, field, bfield in [('heading', 'text', 'name'), ('text', 'html', 'name'),
                                     ('text', 'html', 'price'), ('image', 'src', 'image')]:
            env = {'schema': manifest.PAGE_BINDINGS_ITEM_SCHEMA,
                   'content': {'en': {field: {**ITEM, 'field': bfield}}}}
            self.assertEqual(manifest.page_binding_problems(env, ntype, ('en', 'ar')), [])

    def test_v1_envelope_rejects_bad_shapes(self):
        base = {'schema': manifest.PAGE_BINDINGS_ITEM_SCHEMA, 'content': {'en': {'text': dict(ITEM)}}}
        bad = [
            {**base, 'content': {'en': {'href': dict(ITEM)}}},                      # unsupported target
            {**base, 'content': {'en': {'text': {**ITEM, 'field': 'price'}}}},     # price not bindable to heading
            {**base, 'content': {'en': {'text': {**ITEM, 'item_key': 'x; drop'}}}},
            {**base, 'content': {'en': {'text': {k: v for k, v in ITEM.items() if k != 'item_key'}}}},
            {**base, 'content': {'en': {'text': {**ITEM, 'extra': 1}}}},
            {**base, 'content': {'en': {'text': {**ITEM, 'on_missing': 'guess'}}}},
            {**base, 'content': {'en': {'text': {**ITEM, 'mode': 'static'}}}},
        ]
        for env in bad:
            self.assertTrue(manifest.page_binding_problems(env, 'heading', ('en', 'ar')), env)
        # v1 targets that are not headings at all
        for ntype in ['button', 'gallery', 'section']:
            self.assertTrue(manifest.page_binding_problems(base, ntype, ('en', 'ar')), ntype)
        # v0 envelope still refused on non-heading nodes (no regression)
        v0 = {'schema': manifest.PAGE_BINDINGS_SCHEMA, 'content': {'en': {'text': dict(B)}}}
        self.assertTrue(manifest.page_binding_problems(v0, 'text', ('en', 'ar')))


class WiringTests(unittest.IsolatedAsyncioTestCase):
    def ctx(self):
        return r.SourceContext(A, 'en', frozenset({'inventory'}))

    def scalar_reg(self, calls):
        async def read(*_):
            calls.append(1)
            return None
        return r.ProviderRegistry((r.Provider('site', CONTRACT, read, True),))

    async def test_v1_binding_fails_closed_without_item_resolver(self):
        calls = []
        with self.assertRaises(r.SourceUnavailable):
            await m.resolve_tree(item_tree(), self.scalar_reg(calls), self.ctx(), validate)
        self.assertEqual(calls, [])

    async def test_v1_happy_path_fills_and_strips_envelope(self):
        items = FakeItems('Fixture Card Widget')
        source = item_tree()
        before = copy.deepcopy(source)
        out = await m.resolve_tree(source, self.scalar_reg([]), self.ctx(), validate, items)
        leaf = out_leaf(out)
        self.assertEqual(leaf['content']['en']['text'], 'Fixture Card Widget')
        self.assertNotIn('bindings', leaf)
        self.assertEqual(source, before)
        self.assertEqual(validate(out), [])

    async def test_v1_resolve_omitted_language_keeps_static(self):
        items = FakeItems('Widget')
        out = await m.resolve_tree(item_tree(), self.scalar_reg([]), r.SourceContext(A, 'ar', frozenset({'inventory'})), validate, items)
        self.assertEqual(out_leaf(out)['content']['en']['text'], 'static fallback')
        self.assertEqual(items.resolved, [])

    async def test_v1_missing_record_hides_element(self):
        items = FakeItems(None)
        out = await m.resolve_tree(item_tree(), self.scalar_reg([]), self.ctx(), validate, items)
        self.assertEqual(out['children'][0]['children'][0]['children'], [])

    async def test_pre_read_validation_runs_before_any_provider_read(self):
        # One valid v1 binding plus a second, invalid one: no scalar provider
        # read and no item resolve may happen for either.
        calls = []
        items = FakeItems(fail_validate=True)
        source = item_tree()
        second = copy.deepcopy(source['children'][0]['children'][0]['children'][0])
        second['id'] = 'n_leaf01'
        source['children'][0]['children'][0]['children'].append(second)
        with self.assertRaises(r.SourceUnavailable):
            await m.resolve_tree(source, self.scalar_reg(calls), self.ctx(), validate, items)
        self.assertEqual(calls, [])
        self.assertEqual(items.resolved, [])

    async def test_v1_never_calls_scalar_registry(self):
        calls = []
        items = FakeItems('Widget')
        await m.resolve_tree(item_tree(), self.scalar_reg(calls), self.ctx(), validate, items)
        self.assertEqual(calls, [])

    async def test_hostile_item_target_fails_before_any_read(self):
        calls = []
        items = FakeItems()
        for field in ['href', 'sql', 'html']:
            source = item_tree()
            source['children'][0]['children'][0]['children'][0]['bindings']['content']['en'] = {field: dict(ITEM)}
            with self.assertRaises(r.SourceUnavailable):
                await m.resolve_tree(source, self.scalar_reg(calls), self.ctx(), validate, items)
        self.assertEqual(calls, [])
        self.assertEqual(items.resolved, [])


class ScopedItemValidateTests(unittest.TestCase):
    """Pre-read checks of the real resolver: no database access."""

    def setUp(self):
        self.items = im.ScopedItems(db=None)
        self.ctx = r.SourceContext(A, 'en', frozenset({'inventory'}))

    def test_accepts_supported_combinations(self):
        for field, bfield in [('text', 'name'), ('html', 'name'), ('html', 'price'), ('src', 'image')]:
            self.items.validate(self.ctx, {**ITEM, 'field': bfield}, field)

    def test_refuses_mismatched_field_target(self):
        for field, bfield in [('text', 'price'), ('text', 'image'), ('src', 'name'), ('html', 'image')]:
            with self.assertRaises(r.SourceUnavailable):
                self.items.validate(self.ctx, {**ITEM, 'field': bfield}, field)

    def test_refuses_other_modules_sources_and_inactive_module(self):
        for binding in [{**ITEM, 'module': 'site'}, {**ITEM, 'source': 'orders'}, {**ITEM, 'field': 'cost'}]:
            with self.assertRaises(r.SourceUnavailable):
                self.items.validate(self.ctx, binding, 'text')
        with self.assertRaises(r.SourceUnavailable):
            self.items.validate(r.SourceContext(A, 'en', frozenset()), ITEM, 'text')


if __name__ == '__main__':
    unittest.main()
