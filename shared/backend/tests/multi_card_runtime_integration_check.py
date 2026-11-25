import os,sys,copy,json,unittest,asyncio
from pathlib import Path
from uuid import UUID
from unittest.mock import AsyncMock,patch,MagicMock
os.environ.setdefault('DATABASE_URL','postgresql+asyncpg://unused:unused@127.0.0.1/unused');os.environ.setdefault('SECRET_KEY','offline-test-not-signing');os.environ['VERCEL']='1';sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from card_runtime_integration_check import tree,A,PLAN
from app.platform.site.storefront import card_runtime as c
from app.framework.storefront_runtime import SourceContext,SourceUnavailable,ProviderRegistry
from app.activities.general.modules.inventory.storefront import cards as provider
from app.platform.tenancy.context import current_tenant_id
P='00000000-0000-4000-8000-000000000011';Q='00000000-0000-4000-8000-000000000012'
def multi():
 t=tree();row=copy.deepcopy(t['children'][0])
 def rename(n):
  n['id']=n['id'].replace('00','11')
  for child in n.get('children',[]):rename(child)
 rename(row);second=row['children'][0];second['card']['content']['en']['targets']={k:v.replace('00','11') for k,v in PLAN['targets'].items()}
 # rename also targets without 00 suffix to distinct IDs
 def uniq(n):
  if n['id'] in ('n_price0','n_image0'):n['id']=n['id']+'1'
  for child in n.get('children',[]):uniq(child)
 uniq(row);second['card']['content']['en']['targets'].update(price='n_price01',image='n_image01')
 t['children'].append(row);t['children'][0]['children'][0]['card']['content']['en']['products']=[P];second['card']['content']['en']['products']=[Q];return t
ctx=SourceContext(A,'en',frozenset({'inventory'}))
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_distinct_sections_and_empty_and_mapping_fixture(self):
  source=multi();before=copy.deepcopy(source)
  async def read(db,context,limit,products):return [{'item_key':products[0],'name':'First section product' if products==[P] else 'Second section product','price':None,'image':None}]
  with patch.object(c,'scalar_registry',return_value=ProviderRegistry(())),patch.object(c,'read_cards',side_effect=read):out=await c.resolve_cards(None,source,ctx)
  self.assertEqual(source,before);self.assertEqual(out['children'][0]['children'][0]['children'][0]['content']['en']['text'],'First section product');self.assertEqual(out['children'][1]['children'][0]['children'][0]['content']['en']['text'],'Second section product')
  async def empty_first(db,context,limit,products):return [] if products==[P] else await read(db,context,limit,products)
  with patch.object(c,'scalar_registry',return_value=ProviderRegistry(())),patch.object(c,'read_cards',side_effect=empty_first):empty=await c.resolve_cards(None,source,ctx)
  self.assertEqual(len(empty['children']),1)
  self.assertEqual(len(out['children']),2)
 async def test_all_languages_bounds_and_invalid_subset_before_reads(self):
  cases=[];t=multi();t['children'][1]['children'][0]['card']['content']['ar']={**copy.deepcopy(PLAN),'products':['bad']};cases.append((t,ctx))
  t=multi();t['children'][1]['children'][0]['card']['content']['en']['products']=[Q,Q];cases.append((t,ctx))
  t=multi();t['children'][0]['children'][0]['card']['content']['ar']=copy.deepcopy(t['children'][0]['children'][0]['card']['content']['en']);cases.append((t,SourceContext(A,'ar',frozenset({'inventory'}))))
  t=multi();third=copy.deepcopy(t['children'][1])
  def suffix(n,tail):
   n['id']=n['id']+tail
   if n.get('card'):
    for plan in n['card']['content'].values():plan['targets']={k:v+tail for k,v in plan['targets'].items()}
   for child in n.get('children',[]):suffix(child,tail)
  suffix(third,'2');t['children'].append(third)
  for row in t['children']:row['children'][0]['card']['content']['en']['limit']=6
  cases.append((t,ctx))
  t=multi();extra=[{'id':'n_extra'+str(i),'type':'heading','settings':{},'content':{}} for i in range(475)];t['children'].append({'id':'n_exrow','type':'columns','settings':{},'content':{},'children':[{'id':'n_excol','type':'column','settings':{},'content':{},'children':extra}]});cases.append((t,ctx))
  for t,context in cases:
   read=AsyncMock()
   with patch.object(c,'scalar_registry',return_value=ProviderRegistry(())),patch.object(c,'read_cards',read):
    with self.assertRaises(SourceUnavailable):await c.resolve_cards(None,t,context)
   read.assert_not_awaited()
 async def test_subset_is_consent_intersection_not_new_grant(self):
  token=current_tenant_id.set(A)
  try:
   db=AsyncMock();db.scalar.return_value=json.dumps({'schema':provider.SCHEMA,'products':[P],'show_price':False,'show_image':False,'currency':None})
   # User-approved revocation semantics (2026-11-24 15:03): a valid but no-longer
   # consented selection drops out instead of failing the page; only malformed
   # selections (duplicates, invalid identities, wrong types) stay fail-closed.
   for subset in [[P,P],['BAD'],[True]]:
    with self.assertRaises(SourceUnavailable):await provider.read_cards(db,ctx,3,subset)
   db.execute.assert_not_awaited();self.assertEqual(await provider.read_cards(db,ctx,3,[Q]),[]);self.assertEqual(await provider.read_cards(db,ctx,3,[]),[])
   result=MagicMock();result.all.return_value=[(UUID(P),'Chosen')];db.execute.return_value=result;out=await provider.read_cards(db,ctx,3,[P]);self.assertEqual(out[0]['name'],'Chosen');self.assertEqual(list(db.execute.call_args.args[0].compile().params.values())[-2:],[ [UUID(P)],3])
  finally:current_tenant_id.reset(token)
if __name__=='__main__':unittest.main()
