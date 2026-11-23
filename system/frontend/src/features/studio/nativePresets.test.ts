import {it,expect} from 'vitest';
import {toPageTree} from './pagetree';
import {initialProject} from './model';
import {changeStructure} from './nativeStructure';
import {nativeNodes,nativeUndo,assertNativeTree} from './nativeTree';
import {readableName} from './nativePresets';
it('adds editable presets with unique IDs while leaving prior content untouched',()=>{
 const tree=toPageTree(initialProject),original=structuredClone(tree);
 let state={tree,past:[] as typeof tree[],future:[] as typeof tree[]};
 for(const preset of ['hero','story','callout'] as const){const before=state;state=changeStructure(state,{kind:'preset',preset});expect(nativeUndo(state).tree).toEqual(before.tree);assertNativeTree(state.tree);}
 expect(state.tree.children!.slice(0,tree.children!.length)).toEqual(tree.children);
 const ids=nativeNodes(state.tree).map(n=>n.id);expect(new Set(ids).size).toBe(ids.length);expect(tree).toEqual(original);
});
it('uses readable content names without exposing markup',()=>{
 expect(readableName({id:'n_test',type:'text',settings:{},content:{en:{html:'<p>Hello <b>world</b></p>'}}})).toBe('Hello world');
});
