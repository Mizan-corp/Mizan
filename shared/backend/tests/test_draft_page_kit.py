"""Fixed first-party starter contract, no database or publication effects."""
import unittest
from fastapi import HTTPException
from app.platform.site.page_kits import make_pages,kit_catalog
from app.platform.site.service import check_tree
class DraftKitTests(unittest.TestCase):
 def test_exact_four_native_independent_pages(self):
  pages=make_pages('my-site');self.assertEqual([p['slug'] for p in pages],['my-site-home','my-site-products','my-site-about','my-site-contact'])
  self.assertEqual(len(kit_catalog()['items']),2)
  for page in pages:
   check_tree(page['tree']);self.assertEqual(set(page),{'slug','titles','tree'});self.assertEqual(set(page['titles']),{'en'})
   self.assertNotIn('binding',str(page));self.assertNotIn('checkout',str(page['tree']))
 def test_tech_pages_native_and_fixed(self):
  from app.platform.site.tech_kit import theme
  pages=make_pages('tech','tech-business-v0')
  self.assertEqual([p['slug'] for p in pages],['tech-home','tech-products','tech-services','tech-contact'])
  from app.platform.site.service import check_settings
  self.assertEqual(check_settings(theme('tech')),theme('tech'))
  for page in pages:
   check_tree(page['tree'])
   self.assertNotIn('bindings',str(page));self.assertNotIn('repeat',str(page))
  self.assertEqual([v['href'] for v in theme('tech')['header']['links']],['/'+p['slug'] for p in pages])
 def test_native_card_surface_and_renderer(self):
  from app.platform.site.tech_kit import make_tech_pages
  from app.platform.site.render import _render_node
  tree=make_tech_pages('tech')[1]['tree']
  markup=_render_node(tree,'en','desktop')
  self.assertIn('mz-background-card',markup);self.assertIn('mz-rounded',markup)
  card=tree['children'][1]['children'][0]
  card['settings']['desktop']['background']='url(https://bad.test)'
  with self.assertRaises(HTTPException):check_tree(tree)
 def test_all_columns_keep_mobile_padding(self):
  from app.platform.site.tech_kit import make_tech_pages
  for page in make_tech_pages('tech'):
   stack=[page['tree']]
   while stack:
    node=stack.pop()
    if node.get('type')=='column':self.assertEqual(node.get('settings',{}).get('mobile',{}).get('padding'),'s',node.get('id'))
    stack.extend(node.get('children') or [])
 def test_products_page_has_card_ready_selected_section(self):
  from app.platform.site.tech_kit import make_tech_pages
  tree=make_tech_pages('tech')[1]['tree']
  cols=[r['children'][0] for r in tree['children'] if r.get('type')=='columns' and len(r['children'])==1 and r['children'][0].get('settings',{}).get('desktop',{}).get('background')=='card']
  self.assertEqual(len(cols),1)
  col=cols[0]
  self.assertEqual(col['type'],'column')
  self.assertEqual([c['type'] for c in col['children']],['image','heading','text'])
  self.assertIn('Selected product name',str(col))
  def walk(node):
   self.assertNotIn('card',node)
   for child in node.get('children',[]):walk(child)
  walk(tree)
 def test_no_shared_object_state(self):
  first=make_pages('one');first[0]['tree']['settings']['changed']=True
  self.assertNotIn('changed',make_pages('one')[0]['tree']['settings'])
 def test_prefix_validation(self):
  for prefix in ['','../x','Upper','x y','x--y','a'*41]:
   with self.assertRaises(HTTPException):make_pages(prefix)
if __name__=='__main__':unittest.main()
