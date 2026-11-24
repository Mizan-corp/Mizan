import os,sys,asyncio,importlib.util,json,unittest
from pathlib import Path
from uuid import UUID
os.environ.setdefault('DATABASE_URL','postgresql+asyncpg://unused:unused@127.0.0.1/unused');os.environ.setdefault('SECRET_KEY','offline-provider-test-not-used-for-signing');os.environ['VERCEL']='1';sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.registry import load_all_models
load_all_models()
from app.framework.storefront_runtime import SourceContext,SourceUnavailable,ProviderRegistry
from app.framework.storefront_collections import CollectionRuntime
from app.platform.tenancy.context import current_tenant_id
from unittest.mock import AsyncMock
ROOT=Path(__file__).resolve().parents[1]/'app'
mods=[]
for name,path in [('core_profile',ROOT/'platform/core/storefront/provider.py'),('inventory_catalog',ROOT/'activities/general/modules/inventory/storefront/provider.py')]:
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);mods.append(m)
c,i=mods;A=UUID('00000000-0000-4000-8000-000000000001');Z=UUID('00000000-0000-4000-8000-000000000002')
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_default_no_exposure_and_exact_profile(self):
  self.assertEqual(c.profile_projection(None),{'display_name':None,'tagline':None});self.assertEqual(i.publication_ids(None),{'products':(),'categories':()})
  for raw in ['{}','null',json.dumps({'schema':c.SCHEMA,'display_name':'X','tagline':None,'salary':'secret'})]:
   with self.assertRaises(SourceUnavailable):c.profile_projection(raw)
  self.assertEqual(c.profile_projection(json.dumps({'schema':c.SCHEMA,'display_name':'Opt-in brand','tagline':'Chosen text'}))['display_name'],'Opt-in brand')
 async def test_selection_unknown_private_duplicate_invalid_fail_closed(self):
  for patch in [{'products':[str(A),str(A)]},{'products':['bad']},{'cost':True},{'products':[str(A)]*201}]:
   with self.assertRaises(SourceUnavailable):i.publication_ids(json.dumps({'schema':i.SCHEMA,'products':[],'categories':[],**patch}))
 async def test_inventory_inactive_and_tenant_mismatch_before_query(self):
  db=AsyncMock();runtime=CollectionRuntime(i.inventory_providers(db));token=current_tenant_id.set(A)
  try:
   for ctx in [SourceContext(A,'en',frozenset()),SourceContext(Z,'en',frozenset({'inventory'}))]:
    with self.assertRaises(SourceUnavailable):await runtime.items(ctx,'inventory','products',8)
   db.scalar.assert_not_awaited();db.execute.assert_not_awaited()
  finally:current_tenant_id.reset(token)
 async def test_empty_selection_queries_no_product_rows(self):
  db=AsyncMock();db.scalar.return_value=None;runtime=CollectionRuntime(i.inventory_providers(db));token=current_tenant_id.set(A)
  try:self.assertEqual(await runtime.items(SourceContext(A,'en',frozenset({'inventory'})),'inventory','products',8),());db.execute.assert_not_awaited()
  finally:current_tenant_id.reset(token)
 async def test_trusted_queries_project_only_id_and_name_explicit_tenant_active(self):
  from unittest.mock import MagicMock
  db=AsyncMock();db.scalar.return_value=json.dumps({'schema':i.SCHEMA,'products':[str(A)],'categories':[]});result=MagicMock();result.all.return_value=[(A,'Chosen item')];db.execute.return_value=result;runtime=CollectionRuntime(i.inventory_providers(db));token=current_tenant_id.set(A)
  try:
   items=await runtime.items(SourceContext(A,'en',frozenset({'inventory'})),'inventory','products',8);self.assertEqual(dict(items[0].values),{'name':'Chosen item'});sql=str(db.execute.call_args.args[0]);self.assertIn('products.tenant_id',sql);self.assertIn('products.is_active IS true',sql)
   for forbidden in ['cost_price','wholesale_price','shelf_number','barcode','stock_balance']:self.assertNotIn(forbidden,sql)
  finally:current_tenant_id.reset(token)
 async def test_core_provider_scoped_and_no_invoice_fallback(self):
  db=AsyncMock();db.scalar.return_value=None;runtime=ProviderRegistry((c.core_provider(db),));token=current_tenant_id.set(A);b={'mode':'dynamic','module':'core','source':'website_profile','field':'display_name','on_missing':'hide'};target={'type':'text','semantic':'plain_text','cardinality':'one','element':'heading'}
  try:
   self.assertIsNone(await runtime.resolve(SourceContext(A,'en',frozenset()),b,target));self.assertEqual(db.scalar.await_count,1)
   with self.assertRaises(SourceUnavailable):await runtime.resolve(SourceContext(Z,'en',frozenset()),b,target)
   self.assertEqual(db.scalar.await_count,1)
  finally:current_tenant_id.reset(token)
unittest.main()
