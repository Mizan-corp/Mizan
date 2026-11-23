import {it,expect} from 'vitest';
import {toPageTree} from './pagetree';
import {initialProject} from './model';
import {blockCatalog,templateCatalog,createTemplate} from './nativePresets';
import {changeStructure} from './nativeStructure';
import {nativeNodes,nativeUndo,nativeRedo,assertNativeTree} from './nativeTree';
it('inserts every library block without changing existing content and allocates unique IDs',()=>{
 let state={tree:toPageTree(initialProject),past:[] as ReturnType<typeof toPageTree>[],future:[] as ReturnType<typeof toPageTree>[]};
 for(const item of blockCatalog){const before=structuredClone(state.tree);state=changeStructure(state,{kind:'preset',preset:item.id});assertNativeTree(state.tree);expect(state.tree.children!.slice(0,-1)).toEqual(before.children);expect(nativeUndo(state).tree).toEqual(before);expect(new Set(nativeNodes(state.tree).map(n=>n.id)).size).toBe(nativeNodes(state.tree).length)}
});
it('complete templates retain root identity/metadata and are reversible native compositions',()=>{
 const tree=toPageTree(initialProject);tree.content.ar={};const original=structuredClone(tree);
 for(const item of templateCatalog){const state=changeStructure({tree,past:[],future:[]},{kind:'template',template:item.id});assertNativeTree(state.tree);expect(state.tree.id).toBe(tree.id);expect(state.tree.content).toEqual(tree.content);expect(state.tree.settings).toEqual(tree.settings);expect(state.tree.children).toHaveLength(4);expect(nativeNodes(state.tree).filter(n=>n.type==='heading'&&n.settings.desktop?.level===1)).toHaveLength(1);expect(nativeUndo(state).tree).toEqual(original);expect(nativeRedo(nativeUndo(state)).tree).toEqual(state.tree);expect(nativeNodes(state.tree).slice(1).some(n=>nativeNodes(tree).some(t=>t.id===n.id))).toBe(false)}
 expect(tree).toEqual(original);
});
it('rejects unknown templates without mutating source',()=>{const tree=toPageTree(initialProject),original=structuredClone(tree);expect(()=>createTemplate(tree,'bad' as never)).toThrow();expect(tree).toEqual(original)});
