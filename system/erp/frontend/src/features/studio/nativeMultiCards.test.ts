import {it,expect} from 'vitest';
import fixtures from './nativeMultiCards.fixture.json';
import {assertNativeTree} from './nativeTree';
import {validResolvedTree} from './nativeBindings';
import {nativeProjectionMap} from './nativeProjectionMap';
import type {PageNode} from './pagetree';
const f=fixtures as unknown as Record<string,PageNode>;
it('validates independently selected actual Python section projections and maps the correct template',()=>{
 assertNativeTree(f.source);
 for(const key of ['full','emptyFirst']){
  expect(validResolvedTree(f.source,f[key],'en')).toBe(true);
  const map=nativeProjectionMap(f.source,f[key],'en');
  for(const row of f[key].children!){const original=f.source.children!.find(n=>n.id===row.id)!;expect(map[row.children![0].children![0].id]).toBe(original.children![0].children![0].id)}
 }
});
it('rejects new metadata, duplicate selection and invalid identity in any section language',()=>{
 for(const change of [(p:Record<string,unknown>)=>p.products=['bad'],(p:Record<string,unknown>)=>p.products=['00000000-0000-4000-8000-000000000011','00000000-0000-4000-8000-000000000011'],(p:Record<string,unknown>)=>p.sql='no']){const source=structuredClone(f.source);change(source.children![1].children![0].card!.content.en!);expect(()=>assertNativeTree(source)).toThrow()}
 const changed=structuredClone(f.full);changed.children![1].content={en:{html:'unreviewed'}};expect(validResolvedTree(f.source,changed,'en')).toBe(false);expect(nativeProjectionMap(f.source,changed,'en')).toEqual({});
});
