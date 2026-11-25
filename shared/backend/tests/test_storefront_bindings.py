"""Projection only; no storage schema/API support claimed."""
import copy
import importlib.util
import pathlib
import sys
import unittest
from test_storefront_runtime import r,CONTRACT,B,A
ROOT=pathlib.Path(__file__).resolve().parents[1]

def tree():return {'id':'n_root0','type':'section','settings':{},'content':{},'children':[{'id':'n_row00','type':'columns','settings':{},'content':{},'children':[{'id':'n_col00','type':'column','settings':{},'content':{},'children':[{'id':'n_heading','type':'heading','settings':{},'content':{'en':{'text':'static fallback'},'ar':{'text':'ثابت'}},'bindings':{'schema':'mizan.page-bindings.experimental.v0','content':{'en':{'text':copy.deepcopy(B)}}}}]}]}]}

def validate(t):
    # Actual platform schema loaded below, no fake validator in these tests.
    return manifest.page_problems(t)
spec=importlib.util.spec_from_file_location('native_manifest',ROOT/'app/framework/manifest.py')
manifest=importlib.util.module_from_spec(spec);spec.loader.exec_module(manifest);sys.modules['app.framework.manifest']=manifest

spec=importlib.util.spec_from_file_location('bindings',ROOT/'app/platform/site/storefront/bindings.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class BindingTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_provider_and_platform_validator_projection_preserves_source(self):
        async def read(*_):return {'brand':'<b>Dynamic brand</b>'}
        reg=r.ProviderRegistry((r.Provider('site',CONTRACT,read,True),));source=tree();before=copy.deepcopy(source)
        out=await m.resolve_tree(source,reg,r.SourceContext(A,'en',frozenset()),validate)
        leaf=out['children'][0]['children'][0]['children'][0]
        self.assertEqual(leaf['content']['en']['text'],'<b>Dynamic brand</b>');self.assertNotIn('bindings',leaf);self.assertEqual(source,before);self.assertEqual(validate(out),[])

    async def test_python_renderer_escapes_resolved_text(self):
        spec=importlib.util.spec_from_file_location('site_render',ROOT/'app/platform/site/render.py')
        renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
        async def read(*_):return {'brand':'<script>alert(1)</script> & Brand'}
        reg=r.ProviderRegistry((r.Provider('site',CONTRACT,read,True),))
        out=await m.resolve_tree(tree(),reg,r.SourceContext(A,'en',frozenset()),validate)
        html=renderer.render_page(out,lang='en')
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html);self.assertIn('&amp; Brand',html)

    async def test_versioned_envelope_and_renderer_never_silently_use_static(self):
        source=tree();self.assertEqual(validate(source),[])
        self.assertEqual((ROOT/'app/framework/manifest.py').read_bytes(),next(p/'sdk/python/mizan_sdk/manifest.py' for p in ROOT.parents if (p/'sdk/python/mizan_sdk/manifest.py').exists()).read_bytes())
        for envelope in [{'en':{'text':B}},{'schema':'unknown','content':{'en':{'text':B}}},{'schema':manifest.PAGE_BINDINGS_SCHEMA,'content':{'en':{'text':{**B,'sql':'bad'}}}}]:
            changed=copy.deepcopy(source);changed['children'][0]['children'][0]['children'][0]['bindings']=envelope
            self.assertTrue(validate(changed))
        spec=importlib.util.spec_from_file_location('site_render',ROOT/'app/platform/site/render.py');renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
        for check in [True,False]:
            with self.assertRaises(ValueError):renderer.render_page(source,validate=check)

    async def test_hide_removes_leaf_without_overridable_visibility_or_source_mutation(self):
        async def read(*_):return {'brand':None}
        reg=r.ProviderRegistry((r.Provider('site',CONTRACT,read,True),));source=tree()
        out=await m.resolve_tree(source,reg,r.SourceContext(A,'en',frozenset()),validate)
        self.assertEqual(out['children'][0]['children'][0]['children'],[]);self.assertEqual(len(source['children'][0]['children'][0]['children']),1)
        out=await m.resolve_tree(source,reg,r.SourceContext(A,'ar',frozenset()),validate)
        self.assertEqual(out['children'][0]['children'][0]['children'][0]['content']['ar']['text'],'ثابت')

    async def test_hostile_target_and_static_page_fail_before_provider(self):
        async def read(*_):raise AssertionError('must not execute')
        reg=r.ProviderRegistry((r.Provider('site',CONTRACT,read,True),));ctx=r.SourceContext(A,'en',frozenset())
        for field in ['href','sql','html']:
            source=tree();source['children'][0]['children'][0]['children'][0]['bindings']={'schema':'mizan.page-bindings.experimental.v0','content':{'en':{field:B}}}
            with self.assertRaises(r.SourceUnavailable):await m.resolve_tree(source,reg,ctx,validate)
        source=tree();source['children'][0]['children'][0]['children'][0]['type']='invented'
        with self.assertRaises(r.SourceUnavailable):await m.resolve_tree(source,reg,ctx,validate)

if __name__=='__main__':unittest.main()
