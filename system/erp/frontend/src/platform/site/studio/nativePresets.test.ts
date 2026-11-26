import {it,expect} from 'vitest';
import {toPageTree} from './pagetree';
import {initialProject} from './model';
import {changeStructure} from './nativeStructure';
import {nativeNodes,nativeUndo,assertNativeTree} from './nativeTree';
import {readableName} from './nativePresets';
it('adds editable presets with unique IDs while leaving prior content untouched',()=>{
 const tree=toPageTree(initialProject),original=structuredClone(tree);
 let state={tree,past:[] as typeof tree[],future:[] as typeof tree[]};
 for(const preset of ['hero','story','callout','check_list','icon_list','category_cards'] as const){const before=state;state=changeStructure(state,{kind:'preset',preset});expect(nativeUndo(state).tree).toEqual(before.tree);assertNativeTree(state.tree);}
 expect(state.tree.children!.slice(0,tree.children!.length)).toEqual(tree.children);
 const ids=nativeNodes(state.tree).map(n=>n.id);expect(new Set(ids).size).toBe(ids.length);expect(tree).toEqual(original);
});
it('uses readable content names without exposing markup',()=>{
 expect(readableName({id:'n_test',type:'text',settings:{},content:{en:{html:'<p>Hello <b>world</b></p>'}}})).toBe('Hello world');
});
it('contact_form preset is a valid native tree with a real form block',()=>{
 const tree=toPageTree(initialProject);
 const state=changeStructure({tree,past:[] as typeof tree[],future:[] as typeof tree[]},{kind:'preset',preset:'contact_form'});
 assertNativeTree(state.tree);
 const forms=nativeNodes(state.tree).filter(n=>n.type==='form');
 expect(forms).toHaveLength(1);
 expect(forms[0].settings.desktop?.field_name).toBe(true);
 expect(forms[0].content.en?.email_label).toBe('Email');
 expect(readableName(forms[0])).toBe('Contact us');
});
