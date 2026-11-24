"""Local-only expansion exercised against native validator and Python renderer."""
import copy, importlib.util, sys, unittest
from test_storefront_collections import m as collections, C
from test_storefront_runtime import r,A
from test_storefront_bindings import tree as bound_tree,manifest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('collection_projection',ROOT/'app/platform/site/storefront/collection_projection.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
PLAN={'template_id':'n_heading','module':'site','source':'navigation_labels','field':'label','limit':8,'on_missing':'hide'}
def tree():
 t=bound_tree();leaf=t['children'][0]['children'][0]['children'][0];leaf.pop('bindings');leaf['settings']={'desktop':{'align':'center'},'mobile':{'align':'start'}};return t
class ProjectionTests(unittest.IsolatedAsyncioTestCase):
 async def test_native_expansion_preserves_settings_other_language_and_source(self):
  async def read(*_):return [{'item_key':'home','label':'Home'},{'item_key':'about','label':'About'}]
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));source=tree();before=copy.deepcopy(source)
  out=await p.expand_heading_collection(source,PLAN,runtime,r.SourceContext(A,'en',frozenset()));nodes=out['children'][0]['children'][0]['children']
  self.assertEqual(manifest.page_problems(out),[]);self.assertEqual(source,before);self.assertEqual([n['content']['en']['text'] for n in nodes],['Home','About'])
  self.assertEqual(nodes[0]['settings'],before['children'][0]['children'][0]['children'][0]['settings']);self.assertEqual(nodes[0]['content']['ar']['text'],'ثابت');self.assertNotEqual(nodes[0]['id'],nodes[1]['id'])
 async def test_keys_survive_reorder_and_text_change(self):
  rows=[{'item_key':'home','label':'Home'},{'item_key':'about','label':'About'}]
  async def read(*_):return rows
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));ctx=r.SourceContext(A,'en',frozenset())
  one=await p.expand_heading_collection(tree(),PLAN,runtime,ctx);rows.reverse();rows[0]['label']='Changed'
  two=await p.expand_heading_collection(tree(),PLAN,runtime,ctx)
  one=one['children'][0]['children'][0]['children'];two=two['children'][0]['children'][0]['children'];self.assertEqual(one[0]['id'],two[1]['id']);self.assertEqual(one[1]['id'],two[0]['id'])
 async def test_empty_replaces_template_error_does_not_return_stale_template(self):
  async def read(*_):return []
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));ctx=r.SourceContext(A,'en',frozenset())
  out=await p.expand_heading_collection(tree(),PLAN,runtime,ctx);self.assertEqual(out['children'][0]['children'][0]['children'],[])
  async def fail(*_):raise RuntimeError('source offline')
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,fail,True),))
  with self.assertRaises(RuntimeError):await p.expand_heading_collection(tree(),PLAN,runtime,ctx)
 async def test_invalid_plan_layout_mixed_bindings_and_oversize_before_read(self):
  async def read(*_):raise AssertionError('must not read')
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));ctx=r.SourceContext(A,'en',frozenset())
  for patch in [{'sql':'bad'},{'field':'cost'},{'limit':True},{'limit':9},{'template_id':'n_missing'},{'template_id':'n_col00'},{'on_missing':'static_fallback'}]:
   with self.assertRaises(r.SourceUnavailable):await p.expand_heading_collection(tree(),{**PLAN,**patch},runtime,ctx)
  with self.assertRaises(r.SourceUnavailable):await p.expand_heading_collection(bound_tree(),PLAN,runtime,ctx)
  large=tree();leaves=large['children'][0]['children'][0]['children'];leaves.extend({'id':'n_'+str(i).zfill(5),'type':'heading','content':{},'settings':{}} for i in range(490))
  self.assertEqual(manifest.page_problems(large),[])
  with self.assertRaises(r.SourceUnavailable):await p.expand_heading_collection(large,PLAN,runtime,ctx)
 async def test_renderer_escapes_dynamic_text_and_no_extra_node_fields(self):
  async def read(*_):return [{'item_key':'a','label':'<script>bad()</script> & text'}]
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));out=await p.expand_heading_collection(tree(),PLAN,runtime,r.SourceContext(A,'en',frozenset()))
  spec=importlib.util.spec_from_file_location('collection_renderer',ROOT/'app/platform/site/render.py');renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
  html=renderer.render_page(out,lang='en');self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
 async def test_generated_identity_collision_fails_closed(self):
  async def read(*_):return [{'item_key':'a','label':'A'}]
  runtime=collections.CollectionRuntime((collections.CollectionProvider(C,read,True),));ctx=r.SourceContext(A,'en',frozenset());out=await p.expand_heading_collection(tree(),PLAN,runtime,ctx)
  collision=out['children'][0]['children'][0]['children'][0]['id'];source=tree();source['children'][0]['children'][0]['children'].append({'id':collision,'type':'heading','settings':{},'content':{}})
  with self.assertRaises(r.SourceUnavailable):await p.expand_heading_collection(source,PLAN,runtime,ctx)
if __name__=='__main__':unittest.main()
