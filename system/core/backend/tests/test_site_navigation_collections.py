"""Local site-owned source tests, real provider callable with isolated scoped settings."""
import importlib.util, pathlib, sys, types, unittest
from unittest.mock import AsyncMock, patch
from contextvars import ContextVar
from test_storefront_collections import m
from test_storefront_runtime import r, A, Z
ROOT=pathlib.Path(__file__).resolve().parents[1]
# Load provider against minimal dependencies, never initialize application or DB.
for name in ['app.platform','app.platform.site','app.platform.site.storefront','app.platform.tenancy']:
 if name not in sys.modules:
  module=types.ModuleType(name);module.__path__=[];sys.modules[name]=module
context=types.ModuleType('app.platform.tenancy.context');context.current_tenant_id=ContextVar('collection_test_tenant',default=None)
service=types.ModuleType('app.platform.site.service');service.get_settings=AsyncMock()
with patch.dict(sys.modules,{'app.platform.tenancy.context':context,'app.platform.site.service':service}):
 spec=importlib.util.spec_from_file_location('site_navigation_collections',ROOT/'app/platform/site/storefront/collections.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class NavigationTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.token=context.current_tenant_id.set(A);p.get_settings.reset_mock()
 async def asyncTearDown(self):context.current_tenant_id.reset(self.token)
 async def test_saved_labels_only_order_limit_and_stable_keys(self):
  p.get_settings.return_value={'header':{'brand':'Never expose','links':[{'label':'Home','href':'/'},{'label':'About','href':'/about'}]},'internal':'Never expose'}
  runtime=m.CollectionRuntime((p.navigation_labels_provider(object()),));ctx=r.SourceContext(A,'en',frozenset())
  first=await runtime.items(ctx,'site','navigation_labels',8)
  self.assertEqual([dict(x.values) for x in first],[{'label':'Home'},{'label':'About'}])
  p.get_settings.return_value['header']['links']=[{'label':'About renamed','href':'/about'},{'label':'Home','href':'/'}]
  second=await runtime.items(ctx,'site','navigation_labels',1)
  self.assertEqual(second[0].key,first[1].key);self.assertEqual(dict(second[0].values),{'label':'About renamed'})
 async def test_mismatch_before_settings_read(self):
  runtime=m.CollectionRuntime((p.navigation_labels_provider(object()),))
  with self.assertRaises(r.SourceUnavailable):await runtime.items(r.SourceContext(Z,'en',frozenset()),'site','navigation_labels',8)
  p.get_settings.assert_not_awaited()
 async def test_missing_is_empty_but_corruption_and_duplicate_identity_are_errors(self):
  runtime=m.CollectionRuntime((p.navigation_labels_provider(object()),));ctx=r.SourceContext(A,'en',frozenset())
  p.get_settings.return_value={};self.assertEqual(await runtime.items(ctx,'site','navigation_labels',8),())
  for data in [{'header':None},{'header':{'links':None}},{'header':{'links':[{'label':'a','href':'/a'},{'label':'b','href':'/a'}]}},{'header':{'links':[{'label':'x'*41,'href':'/a'}]}}]:
   p.get_settings.return_value=data
   with self.assertRaises(r.SourceUnavailable):await runtime.items(ctx,'site','navigation_labels',8)
 async def test_read_failure_is_not_empty_success(self):
  runtime=m.CollectionRuntime((p.navigation_labels_provider(object()),));p.get_settings.side_effect=RuntimeError('database offline')
  try:
   with self.assertRaises(RuntimeError):await runtime.items(r.SourceContext(A,'en',frozenset()),'site','navigation_labels',8)
  finally:p.get_settings.side_effect=None
if __name__=='__main__':unittest.main()
