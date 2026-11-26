import importlib.util,pathlib,sys,unittest,copy
from test_storefront_runtime import r,A,Z
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('app.framework.storefront_collections',ROOT/'app/framework/storefront_collections.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
C={'schema':m.SCHEMA,'module':'site','source':'navigation_labels','key':'item_key','fields':{'label':{'type':'text','semantic':'plain_text','nullable':False,'max_length':40}},'max_items':8}
class CollectionTests(unittest.IsolatedAsyncioTestCase):
 async def test_actual_async_many_preserves_order_and_item_scope(self):
  calls=[]
  async def read(ctx,limit):calls.append((ctx.tenant_id,limit));return [{'item_key':'home','label':'Home'},{'item_key':'about','label':'About'}]
  reg=m.CollectionRuntime((m.CollectionProvider(C,read,True),));ctx=r.SourceContext(A,'en',frozenset());items=await reg.items(ctx,'site','navigation_labels',2)
  self.assertEqual([i.key for i in items],['home','about']);self.assertEqual(reg.text(ctx,items[1],module='site',source='navigation_labels',field='label',on_missing='hide'),'About');self.assertEqual(calls,[(A,2)])
  with self.assertRaises(r.SourceUnavailable):reg.text(r.SourceContext(Z,'en',frozenset()),items[0],module='site',source='navigation_labels',field='label',on_missing='hide')
  with self.assertRaises(r.SourceUnavailable):reg.text(ctx,items[0],module='site',source='private_customers',field='label',on_missing='hide')
 async def test_fail_closed_before_provider_on_inactive_unknown_and_limits(self):
  async def read(*_):raise AssertionError('must not execute')
  reg=m.CollectionRuntime((m.CollectionProvider(C,read),));ctx=r.SourceContext(A,'en',frozenset())
  for module,source,limit in [('site','navigation_labels',1),('unknown','navigation_labels',1),('site','navigation_labels',99),('site','navigation_labels',True)]:
   with self.assertRaises(r.SourceUnavailable):await reg.items(ctx,module,source,limit)
 async def test_projection_oversize_duplicate_keys_private_fields_rejected(self):
  rows=[[{'item_key':'a','label':'A','cost':'private'}],[{'item_key':'a','label':'A'},{'item_key':'a','label':'B'}],[{'item_key':'a','label':123}],[{'item_key':'a','label':'x'*41}],[{'item_key':'a','label':None}],[{'item_key':'../bad','label':'A'}]]
  for value in rows:
   async def read(*_,value=value):return value
   reg=m.CollectionRuntime((m.CollectionProvider(C,read,True),))
   with self.assertRaises(r.ProjectionInvalid):await reg.items(r.SourceContext(A,'en',frozenset()),'site','navigation_labels',2)
 async def test_no_cross_tenant_cache_or_mutable_provider_output(self):
  row={'item_key':'one','label':'Before'}
  async def read(ctx,limit):return [row] if ctx.tenant_id==A else [{'item_key':'other','label':'Other tenant'}]
  reg=m.CollectionRuntime((m.CollectionProvider(C,read,True),));a=await reg.items(r.SourceContext(A,'en',frozenset()),'site','navigation_labels',1);row['label']='After';z=await reg.items(r.SourceContext(Z,'en',frozenset()),'site','navigation_labels',1)
  self.assertEqual(a[0].values['label'],'Before');self.assertEqual(z[0].values['label'],'Other tenant')
 async def test_shape_has_no_expressions_commands_or_private_semantics(self):
  for patch in [{'sql':'bad'},{'max_items':1000},{'key':'label'}]:self.assertTrue(m.collection_problems({**C,**patch}))
  changed=copy.deepcopy(C);changed['fields']['label']['semantic']='supplier_cost';self.assertTrue(m.collection_problems(changed))
 async def test_context_immutable_language_issuer_and_current_activation(self):
  async def read(*_):return [{'item_key':'a','label':'A'}]
  reg=m.CollectionRuntime((m.CollectionProvider(C,read),));ctx=r.SourceContext(A,'en',frozenset({'site'}));item=(await reg.items(ctx,'site','navigation_labels',1))[0]
  with self.assertRaises(TypeError):item.values['label']='changed'
  for wrong in [r.SourceContext(A,'ar',frozenset({'site'})),r.SourceContext(A,'en',frozenset())]:
   with self.assertRaises(r.SourceUnavailable):reg.text(wrong,item,module='site',source='navigation_labels',field='label',on_missing='hide')
  other=m.CollectionRuntime((m.CollectionProvider(C,read),))
  with self.assertRaises(r.SourceUnavailable):other.text(ctx,item,module='site',source='navigation_labels',field='label',on_missing='hide')
if __name__=='__main__':unittest.main()
