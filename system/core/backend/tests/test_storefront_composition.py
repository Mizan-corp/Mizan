"""Mixed module scalar and one collection, validated before any provider read."""
import copy,importlib.util,sys,unittest
from test_collection_repeats import repeated,collections,r,A,ROOT
from test_storefront_runtime import CONTRACT,B
from test_storefront_collections import C
from test_storefront_bindings import m as bindings
sys.modules['app.platform.site.storefront.bindings']=bindings
spec=importlib.util.spec_from_file_location('app.platform.site.storefront.composition',ROOT/'app/platform/site/storefront/composition.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def mixed():
 t=repeated();leaves=t['children'][0]['children'][0]['children'];scalar=copy.deepcopy(leaves[0]);scalar.pop('repeat');scalar['id']='n_brand';scalar['bindings']={'schema':'mizan.page-bindings.experimental.v0','content':{'en':{'text':copy.deepcopy(B)}}};leaves.insert(0,scalar);return t
class CompositionTests(unittest.IsolatedAsyncioTestCase):
 async def test_scalar_and_repeat_exact_native_source_retained(self):
  async def scalar(*_):return {'brand':'Chosen brand'}
  async def rows(*_):return [{'item_key':'a','label':'A'},{'item_key':'b','label':'B'}]
  reg=r.ProviderRegistry((r.Provider('site',CONTRACT,scalar,True),));cr=collections.CollectionRuntime((collections.CollectionProvider(C,rows,True),))
  t=mixed();before=copy.deepcopy(t);out=await m.resolve_composition(t,reg,cr,r.SourceContext(A,'en',frozenset()));self.assertEqual(t,before);leaves=out['children'][0]['children'][0]['children'];self.assertEqual([x['content']['en']['text'] for x in leaves],['Chosen brand','A','B']);self.assertEqual(leaves[0]['content']['ar']['text'],'ثابت')
 async def test_invalid_scalar_or_repeat_in_any_language_precedes_reads(self):
  async def fail(*_):raise AssertionError('provider must not run')
  from test_storefront_collections import C
  reg=r.ProviderRegistry((r.Provider('site',CONTRACT,fail,True),));cr=collections.CollectionRuntime((collections.CollectionProvider(C,fail,True),));ctx=r.SourceContext(A,'en',frozenset())
  t=mixed();t['children'][0]['children'][0]['children'][0]['bindings']['content']['ar']={'text':{**B,'field':'private_cost'}}
  with self.assertRaises(r.SourceUnavailable):await m.resolve_composition(t,reg,cr,ctx)
  t=mixed();t['children'][0]['children'][0]['children'][1]['repeat']['content']['ar']={**t['children'][0]['children'][0]['children'][1]['repeat']['content']['en'],'field':'private_cost'}
  with self.assertRaises(r.SourceUnavailable):await m.resolve_composition(t,reg,cr,ctx)
 async def test_missing_scalar_and_empty_collection_have_no_fallback(self):
  from test_storefront_collections import C
  async def scalar(*_):return {'brand':None}
  async def rows(*_):return []
  reg=r.ProviderRegistry((r.Provider('site',CONTRACT,scalar,True),));cr=collections.CollectionRuntime((collections.CollectionProvider(C,rows,True),));out=await m.resolve_composition(mixed(),reg,cr,r.SourceContext(A,'en',frozenset()));self.assertEqual(out['children'][0]['children'][0]['children'],[])
 async def test_same_node_multiple_repeat_and_aggregate_bounds_refuse_before_reads(self):
  async def fail(*_):raise AssertionError('provider must not run')
  reg=r.ProviderRegistry((r.Provider('site',CONTRACT,fail,True),));cr=collections.CollectionRuntime((collections.CollectionProvider(C,fail,True),));ctx=r.SourceContext(A,'en',frozenset())
  t=mixed();leaves=t['children'][0]['children'][0]['children'];leaves[1]['bindings']=copy.deepcopy(leaves[0]['bindings'])
  with self.assertRaises(r.SourceUnavailable):await m.resolve_composition(t,reg,cr,ctx)
  t=mixed();leaves=t['children'][0]['children'][0]['children'];extra=copy.deepcopy(leaves[1]);extra['id']='n_second';leaves.append(extra)
  with self.assertRaises(r.SourceUnavailable):await m.resolve_composition(t,reg,cr,ctx)
  t=mixed();leaves=t['children'][0]['children'][0]['children'];leaves.extend({'id':'n_'+str(i).zfill(5),'type':'heading','settings':{},'content':{}} for i in range(490))
  with self.assertRaises(r.SourceUnavailable):await m.resolve_composition(t,reg,cr,ctx)
 async def test_source_failure_never_falls_back_to_partial_or_static(self):
  async def scalar(*_):raise RuntimeError('offline scalar')
  async def rows(*_):return [{'item_key':'a','label':'A'}]
  reg=r.ProviderRegistry((r.Provider('site',CONTRACT,scalar,True),));cr=collections.CollectionRuntime((collections.CollectionProvider(C,rows,True),));source=mixed();before=copy.deepcopy(source)
  with self.assertRaises(RuntimeError):await m.resolve_composition(source,reg,cr,r.SourceContext(A,'en',frozenset()))
  self.assertEqual(source,before)
if __name__=='__main__':unittest.main()
