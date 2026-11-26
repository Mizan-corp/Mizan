"""Offline tests using actual inventory/file models, no field opt-in inferred."""
import os,sys,json,unittest
from pathlib import Path
from uuid import UUID
from decimal import Decimal
from unittest.mock import AsyncMock,MagicMock
os.environ.setdefault('DATABASE_URL','postgresql+asyncpg://unused:unused@127.0.0.1/unused');os.environ.setdefault('SECRET_KEY','offline-test-not-used-for-signing');os.environ['VERCEL']='1';sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.registry import load_all_models
load_all_models()
from app.activities.general.modules.inventory.storefront import cards as c
from app.framework.storefront_runtime import SourceContext,SourceUnavailable
from app.platform.tenancy.context import current_tenant_id
A=UUID('00000000-0000-4000-8000-000000000001');B=UUID('00000000-0000-4000-8000-000000000002');P=UUID('00000000-0000-4000-8000-000000000003')
def policy(**patch):return json.dumps({'schema':c.SCHEMA,'products':[str(P)],'show_price':False,'show_image':False,'currency':None,**patch})
class Tests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):self.t=current_tenant_id.set(A);self.ctx=SourceContext(A,'en',frozenset({'inventory'}));self.db=AsyncMock()
 async def asyncTearDown(self):current_tenant_id.reset(self.t)
 async def test_default_has_no_field_or_record_grants(self):
  self.db.scalar.return_value=None;self.assertEqual(await c.read_cards(self.db,self.ctx,6),[]);self.db.execute.assert_not_awaited()
 async def test_name_only_query_excludes_money_and_media_columns(self):
  self.db.scalar.return_value=policy();r=MagicMock();r.all.return_value=[(P,'Selected name')];self.db.execute.return_value=r
  rows=await c.read_cards(self.db,self.ctx,6);self.assertEqual(rows,[{'item_key':str(P),'name':'Selected name','price':None,'image':None}]);sql=str(self.db.execute.call_args.args[0]);self.assertIn('products.tenant_id',sql);self.assertIn('products.is_active IS true',sql)
  for field in ['retail_price','cost_price','wholesale_price','image_url','shelf_number','extra','barcode']:self.assertNotIn(field,sql)
 async def test_typed_price_exact_explicit_currency_never_cost(self):
  self.db.scalar.return_value=policy(show_price=True,currency='EGP');r=MagicMock();r.all.return_value=[(P,'Selected',Decimal('14.25'))];self.db.execute.return_value=r;out=await c.read_cards(self.db,self.ctx,1);self.assertEqual(out[0]['price']['amount'],'14.25');self.assertEqual(out[0]['price']['currency'],'EGP');sql=str(self.db.execute.call_args.args[0]);self.assertIn('retail_price',sql);self.assertNotIn('cost_price',sql)
 async def test_media_requires_exact_tenant_product_file_and_safe_address(self):
  url=f'/uploads/t/{A}/product_image/{P}-abc.png';self.db.scalar.side_effect=[policy(show_image=True),P];r=MagicMock();r.all.return_value=[(P,'Selected',url)];self.db.execute.return_value=r;out=await c.read_cards(self.db,self.ctx,1);self.assertEqual(out[0]['image']['src'],url);sql=str(self.db.scalar.call_args.args[0]);self.assertIn('workspace_files.tenant_id',sql);self.assertIn('workspace_files.owner_id',sql);self.assertIn('workspace_files.kind',sql);self.assertIn('workspace_files.content_type',sql)
  self.db.scalar.side_effect=[policy(show_image=True),None]
  with self.assertRaises(SourceUnavailable):await c.read_cards(self.db,self.ctx,1)
 async def test_cross_tenant_inactive_and_limit_before_reads(self):
  for context,limit in [(SourceContext(B,'en',frozenset({'inventory'})),1),(SourceContext(A,'en',frozenset()),1),(self.ctx,7),(self.ctx,True)]:
   with self.assertRaises(SourceUnavailable):await c.read_cards(self.db,context,limit)
  self.db.scalar.assert_not_awaited();self.db.execute.assert_not_awaited()
 async def test_exact_policy_no_implicit_new_fields(self):
  for value in [policy(show_price=True),policy(show_image='yes'),policy(currency='EGP'),policy(products=[str(P),str(P)]),policy(products=['bad']),policy(cost=True)]:
   with self.assertRaises(SourceUnavailable):c.card_policy(value)
if __name__=='__main__':unittest.main()
