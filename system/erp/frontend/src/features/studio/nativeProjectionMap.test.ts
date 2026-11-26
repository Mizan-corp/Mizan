import {it,expect} from 'vitest';
import fixtures from './nativeCards.fixture.json';
import {nativeProjectionMap} from './nativeProjectionMap';
import type {PageNode} from './pagetree';
const f=fixtures as unknown as Record<string,PageNode>;
it('maps every verified card copy to editable template without changing source',()=>{const before=JSON.stringify(f.source);const map=nativeProjectionMap(f.source,f.full,'en');for(const copy of f.full.children![0].children!){expect(map[copy.id]).toBe('n_col00');expect(map[copy.children![0].id]).toBe('n_heading');expect(map[copy.children![1].id]).toBe('n_price');expect(map[copy.children![2].id]).toBe('n_image')}expect(JSON.stringify(f.source)).toBe(before)});
it('handles absent optional fields, empty records and refuses unverified copies',()=>{const map=nativeProjectionMap(f.source,f.optional,'en');expect(map[f.optional.children![0].children![0].children![0].id]).toBe('n_heading');expect(Object.values(map)).not.toContain('n_image');expect(nativeProjectionMap(f.source,f.empty,'en')[f.source.id]).toBe(f.source.id);const bad=structuredClone(f.full);bad.children![0].content={en:{html:'bad'}};expect(nativeProjectionMap(f.source,bad,'en')).toEqual({})});
it('maps verified heading-repeat copies and preserves independent siblings',()=>{
 const s:PageNode={id:'n_root00',type:'section',settings:{},content:{},children:[{id:'n_row000',type:'columns',settings:{},content:{},children:[{id:'n_col000',type:'column',settings:{},content:{},children:[{id:'n_name00',type:'heading',settings:{},content:{en:{text:'Static'}},repeat:{schema:'mizan.page-repeat.experimental.v0',content:{en:{module:'inventory',source:'products',field:'name',limit:2,on_missing:'hide'}}}},{id:'n_after0',type:'heading',settings:{},content:{en:{text:'After'}}}]}]}]};
 const out=structuredClone(s),template=out.children![0].children![0].children![0];delete template.repeat;template.id='n_aaaaaaaaaaaaaaaa';template.content.en={text:'One'};const second=structuredClone(template);second.id='n_bbbbbbbbbbbbbbbb';second.content.en={text:'Two'};out.children![0].children![0].children!.splice(1,0,second);
 const map=nativeProjectionMap(s,out,'en');expect(map[template.id]).toBe('n_name00');expect(map[second.id]).toBe('n_name00');expect(map.n_after0).toBe('n_after0');
});
