import copy,importlib.util,sys,unittest,types
from test_collection_projection import tree,PLAN,collections,r,A,ROOT,manifest
pkg=sys.modules.get('app.platform.site.storefront')
if pkg is None:
 pkg=types.ModuleType('app.platform.site.storefront');pkg.__path__=[];sys.modules[pkg.__name__]=pkg
for name in ['collection_projection','repeats']:
 spec=importlib.util.spec_from_file_location('app.platform.site.storefront.'+name,ROOT/'app/platform/site/storefront'/f'{name}.py');mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
p=sys.modules['app.platform.site.storefront.repeats']
from test_storefront_collections import C

def repeated():
 t=tree();plan={k:v for k,v in PLAN.items() if k!='template_id'};t['children'][0]['children'][0]['children'][0]['repeat']={'schema':manifest.PAGE_REPEAT_SCHEMA,'content':{'en':plan}};return t
class RepeatTests(unittest.IsolatedAsyncioTestCase):
 async def test_versioned_native_envelope_resolution_and_static_other_language(self):
  async def read(*_):return [{'item_key':'a','label':'A'}]
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));source=repeated();before=copy.deepcopy(source);self.assertEqual(manifest.page_problems(source),[])
  out=await p.resolve_repeat(source,runtime,r.SourceContext(A,'en',frozenset()));self.assertEqual(out['children'][0]['children'][0]['children'][0]['content']['en']['text'],'A');self.assertEqual(source,before)
  out=await p.resolve_repeat(source,runtime,r.SourceContext(A,'ar',frozenset()));self.assertEqual(out['children'][0]['children'][0]['children'][0]['content']['ar']['text'],'ثابت');self.assertNotIn('repeat',out['children'][0]['children'][0]['children'][0])
  self.assertEqual((ROOT/'app/framework/manifest.py').read_bytes(),next(q/'sdk/python/mizan_sdk/manifest.py' for q in ROOT.parents if (q/'sdk/python/mizan_sdk/manifest.py').exists()).read_bytes())
 async def test_malformed_envelopes_and_inactive_language_rejected_before_read(self):
  async def read(*_):raise AssertionError('must not read')
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));ctx=r.SourceContext(A,'en',frozenset())
  for env in [{'schema':'old','content':{'en':{}}},{'schema':manifest.PAGE_REPEAT_SCHEMA,'content':{}},{'schema':manifest.PAGE_REPEAT_SCHEMA,'content':{'en':{'sql':'bad'}}}]:
   t=repeated();t['children'][0]['children'][0]['children'][0]['repeat']=env;self.assertTrue(manifest.page_problems(t))
   with self.assertRaises(r.SourceUnavailable):await p.resolve_repeat(t,runtime,ctx)
  t=repeated();content=t['children'][0]['children'][0]['children'][0]['repeat']['content'];content['ar']={**content['en'],'field':'supplier_cost'}
  self.assertEqual(manifest.page_problems(t),[])
  with self.assertRaises(r.SourceUnavailable):await p.resolve_repeat(t,runtime,ctx)
 async def test_query_without_matches_shows_empty_state(self):
  async def read(*_):return [{'item_key':'a','label':'Widget'}]
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));ctx=r.SourceContext(A,'en',frozenset())
  out=await p.resolve_repeat(repeated(),runtime,ctx,query='zzz')
  kids=out['children'][0]['children'][0]['children']
  self.assertEqual(len(kids),1);node=kids[0]
  self.assertEqual(node['type'],'text');self.assertIn('zzz',node['content']['en']['html']);self.assertIn('zzz',node['content']['ar']['html'])
  self.assertEqual(manifest.page_problems(out,('en','ar')),[])
 async def test_renderer_refuses_unresolved_even_without_validation(self):
  spec=importlib.util.spec_from_file_location('repeat_renderer',ROOT/'app/platform/site/render.py');renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
  for validate in [True,False]:
   with self.assertRaises(ValueError):renderer.render_page(repeated(),validate=validate)
 async def test_multiple_templates_and_non_column_parent_fail_before_read(self):
  async def read(*_):raise AssertionError('must not read')
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));ctx=r.SourceContext(A,'en',frozenset());t=repeated();leaf=copy.deepcopy(t['children'][0]['children'][0]['children'][0]);leaf['id']='n_other';t['children'][0]['children'][0]['children'].append(leaf)
  with self.assertRaises(r.SourceUnavailable):await p.resolve_repeat(t,runtime,ctx)
if __name__=='__main__':unittest.main()
