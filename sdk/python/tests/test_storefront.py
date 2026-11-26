"""Offline contract tests. No service, source provider or runtime integration claimed."""
import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SDK = ROOT / 'sdk/python/mizan_sdk/storefront.py'
PLATFORM = ROOT / 'system/core/backend/app/framework/storefront.py'
if not PLATFORM.exists():
    PLATFORM = ROOT / 'backend/app/framework/storefront.py'
spec = importlib.util.spec_from_file_location('storefront_contract', SDK)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    return {'schema': module.SCHEMA, 'module': 'example_catalog', 'sources': [
        {'id': 'public_item', 'label': 'Public item', 'exposure': 'public_projection', 'cardinality': 'one',
         'fields': [{'id': 'title', 'label': 'Title', 'type': 'text', 'semantic': 'plain_text',
                     'nullable': False, 'exposure': 'public', 'elements': ['heading', 'text']}]}],
        'pages': [{'id': 'item_detail', 'label': 'Item detail', 'requirement': 'optional', 'source': 'public_item'}]}


class StorefrontContractTests(unittest.TestCase):
    def test_copy_identical(self):
        self.assertEqual(SDK.read_bytes(), PLATFORM.read_bytes())

    def test_valid_metadata_and_module_identity(self):
        self.assertEqual(module.storefront_contract_problems(fixture(), 'example_catalog'), [])
        self.assertTrue(module.storefront_contract_problems(fixture(), 'different'))

    def test_no_provider_urls_scripts_raw_tables_or_commands(self):
        for key in ['provider', 'url', 'sql', 'javascript', 'commands', 'permissions']:
            data = fixture(); data[key] = 'not executed'
            self.assertTrue(module.storefront_contract_problems(data), key)

    def test_exposure_is_explicit_at_source_and_field(self):
        for obj, key in [('source', 'exposure'), ('field', 'exposure')]:
            data = fixture(); target = data['sources'][0] if obj == 'source' else data['sources'][0]['fields'][0]
            del target[key]
            self.assertTrue(module.storefront_contract_problems(data))
        data = fixture(); data['sources'][0]['fields'][0]['exposure'] = 'internal'
        self.assertTrue(module.storefront_contract_problems(data))

    def test_rejects_private_semantics_and_type_only_match(self):
        data = fixture(); field = data['sources'][0]['fields'][0]
        field.update(type='money', semantic='supplier_cost', elements=['price'])
        self.assertTrue(module.storefront_contract_problems(data))

    def test_rejects_wrong_recommendation_and_unknown_nested_data(self):
        data = fixture(); data['sources'][0]['fields'][0]['elements'] = ['price']
        self.assertTrue(module.storefront_contract_problems(data))
        data = fixture(); data['sources'][0]['fields'][0]['example_customer'] = 'private'
        self.assertTrue(module.storefront_contract_problems(data))

    def test_duplicate_source_field_and_page(self):
        for path in ['source', 'field', 'page']:
            data = fixture(); rows = data['sources'] if path == 'source' else data['pages'] if path == 'page' else data['sources'][0]['fields']
            rows.append(copy.deepcopy(rows[0]))
            self.assertTrue(module.storefront_contract_problems(data))

    def test_no_missing_page_source_or_effect_defaults(self):
        data = fixture(); data['pages'][0]['source'] = 'missing'
        self.assertTrue(module.storefront_contract_problems(data))
        data = fixture(); data['pages'][0]['replace_existing'] = True
        self.assertTrue(module.storefront_contract_problems(data))

    def test_finite_bounded_json_and_hostile_shapes(self):
        for data in [None, [], {'x': float('nan')}, {'x': object()}, {'x': 'a' * 70000}]:
            self.assertTrue(module.storefront_contract_problems(data))
        data = fixture(); data['sources'][0]['fields'][0]['type'] = []
        self.assertTrue(module.storefront_contract_problems(data))
        data = fixture(); data['sources'][0]['fields'][0]['elements'] = [{}]
        self.assertTrue(module.storefront_contract_problems(data))

    def test_exact_binding_and_no_mutation(self):
        data = fixture(); before = copy.deepcopy(data)
        binding = {'mode': 'dynamic', 'module': 'example_catalog', 'source': 'public_item', 'field': 'title', 'on_missing': 'hide'}
        target = {'type': 'text', 'semantic': 'plain_text', 'cardinality': 'one', 'element': 'heading'}
        self.assertEqual(module.storefront_binding_problems(binding, data, target), [])
        self.assertEqual(data, before)
        for field, value in [('module', 'other'), ('field', 'missing'), ('on_missing', 'execute'), ('mode', 'static')]:
            changed = dict(binding); changed[field] = value
            self.assertTrue(module.storefront_binding_problems(changed, data, target))
        for field, value in [('type', 'money'), ('semantic', 'supplier_cost'), ('cardinality', 'many'), ('element', 'image')]:
            changed = dict(target); changed[field] = value
            self.assertTrue(module.storefront_binding_problems(binding, data, changed))

    def test_nested_binding_target_values_are_not_expressions(self):
        data = fixture()
        binding = {'mode': 'dynamic', 'module': 'example_catalog', 'source': 'public_item', 'field': 'title', 'on_missing': 'hide'}
        target = {'type': 'text', 'semantic': 'plain_text', 'cardinality': 'one', 'element': 'heading'}
        for value in [None, True, 5, float('nan'), [], {}, {'expression': 'not executed'}, 'a' * 121]:
            for key in binding:
                changed = dict(binding); changed[key] = value
                self.assertTrue(module.storefront_binding_problems(changed, data, target), key)
            for key in target:
                changed = dict(target); changed[key] = value
                self.assertTrue(module.storefront_binding_problems(binding, data, changed), key)

    def test_collection_cannot_bind_scalar_without_item_context(self):
        data = fixture(); data['sources'][0]['cardinality'] = 'many'
        binding = {'mode': 'dynamic', 'module': 'example_catalog', 'source': 'public_item', 'field': 'title', 'on_missing': 'empty'}
        target = {'type': 'text', 'semantic': 'plain_text', 'cardinality': 'one', 'element': 'heading'}
        self.assertTrue(module.storefront_binding_problems(binding, data, target))


if __name__ == '__main__':
    unittest.main()
