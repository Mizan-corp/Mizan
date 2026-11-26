"""Actual module imports and async runtime, no DB connection or fixture writes."""
import os,sys,copy,unittest
from pathlib import Path
from uuid import UUID
from unittest.mock import AsyncMock,patch
os.environ.setdefault('DATABASE_URL','postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY','offline-test-not-used-for-signing')
os.environ['VERCEL']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.registry import load_all_models
load_all_models()
from app.platform.site.storefront import card_runtime as c
from app.framework.manifest import page_problems
from app.framework.storefront_runtime import SourceContext,SourceUnavailable,ProviderRegistry
from app.framework.storefront_values import money_value
from app.platform.site.render import render_document
A=UUID('00000000-0000-4000-8000-000000000001')
PLAN={'module':'inventory','source':'website_cards','limit':3,'targets':{'name':'n_name00','price':'n_price0','image':'n_image0'}}
def node(i,t,children=None,content=None):return {'id':i,'type':t,'settings':{},'content':content or {},**({'children':children} if children is not None else {})}
def tree():
    card=node('n_card00','column',[node('n_name00','heading',content={'en':{'text':'NEVER NAME'}}),node('n_price0','text',content={'en':{'html':'<p>NEVER PRICE</p>'}}),node('n_image0','image',content={'en':{'src':'/never-image.png','alt':'NEVER IMAGE'}})])
    card['card']={'schema':'mizan.page-card.experimental.v0','content':{'en':copy.deepcopy(PLAN)}}
    row=node('n_row000','columns',[card]);row['settings']={'mobile':{'stack':True}}
    return node('n_root00','section',[row])
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_native_schema_and_no_static_renderer_fallback(self):
    t=tree();self.assertEqual(page_problems(t,('en','ar')),[])
    with self.assertRaises(ValueError):render_document(t,{})
 async def test_resolve_native_and_no_optional_static_fallback(self):
    t=tree();before=copy.deepcopy(t);read=AsyncMock(return_value=[{'item_key':'one','name':'Selected','price':money_value('4.25','EGP'),'image':None}])
    with patch.object(c,'scalar_registry',return_value=ProviderRegistry(())),patch.object(c,'read_cards',read):
        out=await c.resolve_cards(None,t,SourceContext(A,'en',frozenset({'inventory'})))
    self.assertEqual(t,before);self.assertEqual(page_problems(out),[]);self.assertEqual(len(out['children'][0]['children'][0]['children']),2)
    html=render_document(out,{},lang='en');self.assertIn('4.25 EGP',html)
    for value in ['NEVER','never-image','"card"']:self.assertNotIn(value,html)
    read.assert_awaited_once()
 async def test_every_language_and_scope_rejected_before_read(self):
    cases=[]
    t=tree();t['children'][0]['children'][0]['card']['content']['ar']={**PLAN,'source':'private'};cases.append(t)
    t=tree();t['children'][0]['children'][0]['children'][0]['bindings']={'schema':'bad'};cases.append(t)
    t=tree();t['children'][0]['children'][0]['repeat']={'schema':'bad'};cases.append(t)
    t=tree();t['children'][0]['children'][0]['card']['content']['en']['targets']['price']='n_root00';cases.append(t)
    for t in cases:
        read=AsyncMock()
        with patch.object(c,'scalar_registry',return_value=ProviderRegistry(())),patch.object(c,'read_cards',read):
            with self.assertRaises(SourceUnavailable):await c.resolve_cards(None,t,SourceContext(A,'en',frozenset({'inventory'})))
        read.assert_not_awaited()
 async def test_missing_language_inactive_duplicate_and_overflow_before_read(self):
    for t,ctx in [(tree(),SourceContext(A,'ar',frozenset({'inventory'}))),(tree(),SourceContext(A,'en',frozenset()))]:
        read=AsyncMock()
        with patch.object(c,'scalar_registry',return_value=ProviderRegistry(())),patch.object(c,'read_cards',read):
            with self.assertRaises(SourceUnavailable):await c.resolve_cards(None,t,ctx)
        read.assert_not_awaited()
 async def test_empty_cards_remove_native_row(self):
    with patch.object(c,'scalar_registry',return_value=ProviderRegistry(())),patch.object(c,'read_cards',AsyncMock(return_value=[])):
        out=await c.resolve_cards(None,tree(),SourceContext(A,'en',frozenset({'inventory'})))
    self.assertEqual(out['children'],[])
 async def test_source_failure_no_partial_result(self):
    with patch.object(c,'scalar_registry',return_value=ProviderRegistry(())),patch.object(c,'read_cards',AsyncMock(side_effect=SourceUnavailable('unavailable'))):
        with self.assertRaises(SourceUnavailable):await c.resolve_cards(None,tree(),SourceContext(A,'en',frozenset({'inventory'})))
if __name__=='__main__':unittest.main()
