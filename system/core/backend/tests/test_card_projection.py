"""Native editable-card render copies, no API or page persistence claim."""
import copy,importlib.util,sys,unittest
from test_collection_projection import tree,ROOT,manifest,r,A
from test_storefront_values import v
sys.modules['app.framework.storefront_values']=v
spec=importlib.util.spec_from_file_location('cards_projection',ROOT/'app/platform/site/storefront/card_projection.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PLAN={'template_id':'n_col00','module':'inventory','source':'website_cards','limit':3,'targets':{'name':'n_heading','price':'n_price','image':'n_image'}}
def source():
 t=tree();leaves=t['children'][0]['children'][0]['children'];leaves.extend([{'id':'n_price','type':'text','settings':{},'content':{'en':{'html':'<p>Static price</p>'}}},{'id':'n_image','type':'image','settings':{},'content':{'en':{'src':'/placeholder.png','alt':'Static image'}}}]);return t
def row(key='one',price=True,image=True):return {'item_key':key,'name':'Chosen <product>','price':v.money_value('12.50','EGP') if price else None,'image':v.media_value(f'/uploads/t/{A}/product_image/x.png','Chosen product',A) if image else None}
class CardProjectionTests(unittest.TestCase):
 def test_ordinary_native_projection_preserves_source_static_languages_and_settings(self):
  t=source();before=copy.deepcopy(t);out=m.project_cards(t,PLAN,[row(),row('two')],r.SourceContext(A,'en',frozenset({'inventory'})));self.assertEqual(t,before);self.assertEqual(manifest.page_problems(out),[]);cards=out['children'][0]['children'];self.assertEqual(len(cards),2);self.assertEqual(cards[0]['children'][0]['content']['en']['text'],'Chosen <product>');self.assertEqual(cards[0]['children'][0]['content']['ar']['text'],'ثابت');self.assertEqual(cards[0]['children'][1]['content']['en']['html'],'<p>12.50 EGP</p>');self.assertEqual(cards[0]['children'][0]['settings'],t['children'][0]['children'][0]['children'][0]['settings']);self.assertNotEqual(cards[0]['id'],cards[1]['id'])
 def test_missing_optional_fields_hidden_not_static_fallback(self):
  out=m.project_cards(source(),PLAN,[row(price=False,image=False)],r.SourceContext(A,'en',frozenset({'inventory'})));self.assertEqual(len(out['children'][0]['children'][0]['children']),1)
  empty=m.project_cards(source(),PLAN,[],r.SourceContext(A,'en',frozenset({'inventory'})));self.assertEqual(empty['children'],[])
 def test_designed_columns_cap_card_tracks(self):
  ctx=r.SourceContext(A,'en',frozenset({'inventory'}))
  t=source();t['children'][0]['settings']={'desktop':{'columns':3}}
  out=m.project_cards(t,PLAN,[row(),row('two'),row('three')],ctx);self.assertEqual(out['children'][0]['settings']['desktop']['columns'],3)
  out=m.project_cards(source(),PLAN,[row(),row('two')],ctx);self.assertEqual(out['children'][0]['settings']['desktop']['columns'],2)
  t=source();t['children'][0]['settings']={'desktop':{'columns':4}}
  out=m.project_cards(t,PLAN,[row(),row('two')],ctx);self.assertEqual(out['children'][0]['settings']['desktop']['columns'],2)
 def test_stable_item_identity_under_reorder_and_name_change(self):
  ctx=r.SourceContext(A,'en',frozenset({'inventory'}));one=m.project_cards(source(),PLAN,[row(),row('two')],ctx);two=m.project_cards(source(),PLAN,[row('two'),{**row(),'name':'Changed'}],ctx);self.assertEqual(one['children'][0]['children'][0]['id'],two['children'][0]['children'][1]['id'])
 def test_invalid_fields_urls_money_duplicates_and_overflow_fail_closed(self):
  ctx=r.SourceContext(A,'en',frozenset({'inventory'}))
  for rows in [[{**row(),'cost':5}],[row(),row()],[{**row(),'price':{'amount':3,'currency':'EGP'}}],[{**row(),'image':{'schema':v.MEDIA_SCHEMA,'src':'https://private.invalid/x.png','alt':'x'}}],[row(str(i)) for i in range(4)]]:
   with self.assertRaises(r.ProjectionInvalid):m.project_cards(source(),PLAN,rows,ctx)
 def test_template_exact_shapes_and_aggregate_bound_preflight(self):
  for patch in [{'sql':'bad'},{'source':'all_products'},{'limit':7},{'targets':{'name':'n_heading','price':'n_heading','image':'n_image'}}]:
   with self.assertRaises(r.SourceUnavailable):m.checked_card_template(source(),{**PLAN,**patch})
  t=source();extra=copy.deepcopy(t['children'][0]);extra['id']='n_otherrow';extra['children'][0]['id']='n_othercol';extra['children'][0]['children']=[{'id':'n_'+str(i).zfill(5),'type':'heading','settings':{},'content':{}} for i in range(485)];t['children'].append(extra)
  with self.assertRaises(r.SourceUnavailable):m.checked_card_template(t,{**PLAN,'limit':6})
if __name__=='__main__':unittest.main()
