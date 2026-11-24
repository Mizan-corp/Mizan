"""Actual async provider calls. No API, persisted binding or UI readiness claim."""
import asyncio
import copy
import importlib.util
import json
import pathlib
import sys
import types
import unittest
from uuid import UUID

ROOT=pathlib.Path(__file__).resolve().parents[1]
for name in ['app','app.framework']:
    if name not in sys.modules:
        mod=types.ModuleType(name);mod.__path__=[];sys.modules[name]=mod
for name in ['storefront','storefront_runtime']:
    spec=importlib.util.spec_from_file_location('app.framework.'+name,ROOT/'app/framework'/f'{name}.py')
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
r=sys.modules['app.framework.storefront_runtime']
CONTRACT=json.loads((ROOT/'app/platform/site/storefront/contract.json').read_text())
T={'type':'text','semantic':'plain_text','cardinality':'one','element':'heading'}
B={'mode':'dynamic','module':'site','source':'appearance','field':'brand','on_missing':'hide'}
A=UUID('00000000-0000-4000-8000-000000000001');Z=UUID('00000000-0000-4000-8000-000000000002')

class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_tenant_context_is_passed_and_values_are_not_cached_across_tenants(self):
        calls=[]
        async def read(ctx,source):
            calls.append((ctx.tenant_id,source));return {'brand':str(ctx.tenant_id)}
        reg=r.ProviderRegistry((r.Provider('site',CONTRACT,read,True),))
        self.assertEqual(await reg.resolve(r.SourceContext(A,'en',frozenset()),B,T),str(A))
        self.assertEqual(await reg.resolve(r.SourceContext(Z,'ar',frozenset()),B,T),str(Z))
        self.assertEqual(len(calls),2)

    async def test_missing_inactive_and_unknown_sources_never_call_provider(self):
        async def read(*_):raise AssertionError('must not run')
        reg=r.ProviderRegistry((r.Provider('site',CONTRACT,read),));ctx=r.SourceContext(A,'en',frozenset())
        self.assertEqual(reg.discover(ctx),[])
        with self.assertRaises(r.SourceUnavailable):await reg.resolve(ctx,B,T)
        ctx=r.SourceContext(A,'en',frozenset({'site'}))
        for patch in [{'field':'supplier_cost'},{'module':'inventory'},{'source':'raw_table'},{'sql':'select *'}]:
            with self.assertRaises(r.SourceUnavailable):await reg.resolve(ctx,{**B,**patch},T)

    async def test_projection_fail_closed_and_missing_behavior(self):
        ctx=r.SourceContext(A,'en',frozenset())
        for data in [{'brand':'ok','password':'private'},{'brand':123},{'brand':'x'*201},[]]:
            async def read(*_,data=data):return data
            reg=r.ProviderRegistry((r.Provider('site',CONTRACT,read,True),))
            with self.assertRaises(r.ProjectionInvalid):await reg.resolve(ctx,B,T)
        async def empty(*_):return {'brand':None}
        reg=r.ProviderRegistry((r.Provider('site',CONTRACT,empty,True),))
        self.assertIsNone(await reg.resolve(ctx,B,T));self.assertEqual(await reg.resolve(ctx,{**B,'on_missing':'empty'},T),'')

    async def test_discovery_copy_is_not_registry_authority(self):
        async def read(*_):return {'brand':'<script>still text</script>'}
        contract=copy.deepcopy(CONTRACT);reg=r.ProviderRegistry((r.Provider('site',contract,read,True),));ctx=r.SourceContext(A,'en',frozenset())
        contract['sources'].clear();reg.discover(ctx)[0]['sources'].clear()
        self.assertEqual(await reg.resolve(ctx,B,T),'<script>still text</script>')
        with self.assertRaises(r.SourceUnavailable):await reg.resolve(ctx,B,{**T,'semantic':'supplier_cost'})
        with self.assertRaises(r.SourceUnavailable):await reg.resolve(ctx,B,{**T,'cardinality':'many'})

    async def test_explicit_tenant_and_duplicate_registration(self):
        for tid in [None,'not-a-uuid']:
            with self.assertRaises(r.SourceUnavailable):r.SourceContext(tid,'en',frozenset())
        async def read(*_):return None
        p=r.Provider('site',CONTRACT,read,True)
        with self.assertRaises(ValueError):r.ProviderRegistry((p,p))

if __name__=='__main__':unittest.main()
