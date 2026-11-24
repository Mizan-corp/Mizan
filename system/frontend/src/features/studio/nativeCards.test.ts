import {describe,it,expect} from 'vitest';
import fixtures from './nativeCards.fixture.json';
import {assertNativeTree,editNativeTree} from './nativeTree';
import {validResolvedTree,hasBindings} from './nativeBindings';
import {changeCard,cardProblem} from './nativeCards';
import type {PageNode} from './pagetree';
const f=fixtures as unknown as Record<string,PageNode>;
describe('native editable product cards',()=>{
 it('accepts actual Python projections for full, missing fields and no records',()=>{assertNativeTree(f.source);expect(hasBindings(f.source)).toBe(true);for(const key of ['full','optional','empty']){assertNativeTree(f[key]);expect(validResolvedTree(f.source,f[key],'en'),key).toBe(true);expect(hasBindings(f[key])).toBe(false)}});
 it('retains template content and editing styles',()=>{const changed=editNativeTree(f.source,{kind:'setting',id:'n_heading',device:'desktop',field:'level',value:2});expect(changed.children![0].children![0].children![0].settings.desktop.level).toBe(2);expect(changed.children![0].children![0].card).toEqual(f.source.children![0].children![0].card)});
 it('refuses arbitrary metadata, price, image, source and replacement structure',()=>{
  for(const mutate of [(x:PageNode)=>x.children![0].settings.desktop!.columns=6,(x:PageNode)=>x.children![0].children![0].children![1].content.en.html='<p>0.00 COST</p>',(x:PageNode)=>x.children![0].children![0].children![2].content.en.src='https://evil.invalid/a.png',(x:PageNode)=>x.children![0].children![0].children![0].content.ar={text:'Changed other language'},(x:PageNode)=>x.children![0].children![0].children!.push(structuredClone(x.children![0].children![0].children![0]))]){const changed=structuredClone(f.full);mutate(changed);expect(validResolvedTree(f.source,changed,'en')).toBe(false)}
 });
 it('refuses missing language and invalid source',()=>{expect(validResolvedTree(f.source,f.full,'ar')).toBe(false);const t=structuredClone(f.source);(t.children![0].children![0].card!.content.en as unknown as {source:string}).source='private';expect(()=>assertNativeTree(t)).toThrow();expect(cardProblem(null,'column')).toBe(true)});
 it('disconnects only current language without changing static content',()=>{const out=changeCard(f.source,'n_col00','en',null);expect(hasBindings(out)).toBe(false);expect(out.children![0].children![0].content).toEqual(f.source.children![0].children![0].content)});
});
