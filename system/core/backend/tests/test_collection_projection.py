"""Local-only expansion exercised against native validator and Python renderer."""
import copy, importlib.util, unittest
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
def card_tree():
 return {'id':'n_root0','type':'section','settings':{},'content':{},'children':[{'id':'n_row00','type':'columns','settings':{},'content':{},'children':[{'id':'n_card0','type':'column','settings':{},'content':{},'children':[
  {'id':'n_head0','type':'heading','settings':{},'content':{'en':{'text':'H'},'ar':{'text':'ح'}}},
  {'id':'n_txt01','type':'text','settings':{},'content':{'en':{'html':'<p>a</p>'},'ar':{'html':'<p>ب</p>'}}},
  {'id':'n_txt02','type':'text','settings':{},'content':{'en':{'html':'<p>b</p>'},'ar':{'html':'<p>ج</p>'}}}]}]}]}
CARD_C={'schema':'mizan.collection.experimental.v0','module':'helpdesk','source':'services','key':'item_key','fields':{'name':{'type':'text','semantic':'plain_text','nullable':False,'max_length':200},'description':{'type':'text','semantic':'plain_text','nullable':True,'max_length':200},'starting_price':{'type':'text','semantic':'plain_text','nullable':True,'max_length':40}},'max_items':24}
CARD_PLAN={'template_id':'n_card0','module':'helpdesk','source':'services','limit':8,'on_missing':'hide'}
CARD_SLOTS={'heading':'name','text':'description','text2':'starting_price'}
class MultiTextSlotCardTests(unittest.IsolatedAsyncioTestCase):
 async def test_ordered_text_slots_fill_successive_children_and_missing_keeps_card(self):
  rows=[{'item_key':'a','name':'AC install','description':'Split unit install','starting_price':'500.00 EGP'},{'item_key':'b','name':'Plumbing visit','description':None,'starting_price':'100.00 EGP'}]
  async def read(*_):return rows
  runtime=collections.CollectionRuntime((collections.CollectionProvider(CARD_C,read,True),));ctx=r.SourceContext(A,'en',frozenset())
  source=card_tree();before=copy.deepcopy(source)
  out=await p.expand_card_collection(source,CARD_PLAN,CARD_SLOTS,runtime,ctx)
  self.assertEqual(manifest.page_problems(out),[]);self.assertEqual(source,before)
  cards=out['children'][0]['children'];self.assertEqual(len(cards),2)
  first=[c['content']['en'] for c in cards[0]['children']]
  self.assertEqual(first[0]['text'],'AC install');self.assertIn('Split unit install',first[1]['html']);self.assertIn('500.00 EGP',first[2]['html'])
  second=cards[1]['children'];self.assertEqual([c['type'] for c in second],['heading','text'])
  self.assertEqual(second[0]['content']['en']['text'],'Plumbing visit');self.assertIn('100.00 EGP',second[1]['content']['en']['html'])
  self.assertNotIn('None',second[1]['content']['en']['html']);self.assertNotEqual(cards[0]['id'],cards[1]['id'])
 async def test_slot_shape_checked_before_any_provider_read(self):
  async def read(*_):raise AssertionError('must not read')
  runtime=collections.CollectionRuntime((collections.CollectionProvider(CARD_C,read,True),));ctx=r.SourceContext(A,'en',frozenset())
  for slots in [{'heading':'name','text':'description','text2':'missing'},{'heading':'name','text':'description','text2':'starting_price','text4':'name'},{'heading':'name'}]:
   with self.assertRaises(r.SourceUnavailable):await p.expand_card_collection(card_tree(),CARD_PLAN,slots,runtime,ctx)
 def test_manifest_accepts_ordered_text_slots_and_rejects_unknown_keys(self):
  t=card_tree();column=t['children'][0]['children'][0]
  column['repeat']={'schema':'mizan.page-repeat.experimental.v1','slots':CARD_SLOTS,'content':{'en':{'module':'helpdesk','source':'services','limit':8,'on_missing':'hide'}}}
  self.assertEqual(manifest.page_problems(t),[])
  column['repeat']['slots']={'heading':'name','text':'description','text4':'starting_price'}
  self.assertTrue(manifest.page_problems(t))
if __name__=='__main__':unittest.main()
