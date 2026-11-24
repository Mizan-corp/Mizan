import {describe,it,expect} from 'vitest';
import {changeRepeat,repeatProblem,repeatSchema,validResolvedTree,hasBindings,type NativeRepeatPlan} from './nativeBindings';
import {assertNativeTree,nativeUndo} from './nativeTree';
import {newPagePayload} from './newPage';
const plan:NativeRepeatPlan={module:'inventory',source:'products',field:'name',limit:8,on_missing:'hide'};
function fixture(){const tree=newPagePayload({title:'Static',slug:'static',language:'en'}).tree;return {tree,id:tree.children![0].children![0].children![0].id}}
describe('native repeats',()=>{
 it('retains static source and undo, explicit repeat envelope',()=>{const {tree,id}=fixture();const next=changeRepeat(tree,id,'en',plan);assertNativeTree(next);expect(hasBindings(next)).toBe(true);expect(changeRepeat(next,id,'en',null)).toEqual(tree);expect(nativeUndo({tree:next,past:[tree],future:[]}).tree).toEqual(tree);});
 it('rejects malformed metadata and overbroad limits',()=>{for(const p of [{...plan,limit:true},{...plan,limit:25},{...plan,sql:'bad'}])expect(repeatProblem({schema:repeatSchema,content:{en:p}},'heading')).toBe(true)});
 it('accepts only bounded exact template projections and refuses settings/static/extra mutations',()=>{const {tree,id}=fixture();const next=changeRepeat(tree,id,'en',plan),out=structuredClone(tree);const leaf=out.children![0].children![0].children![0];leaf.id='n_1234567890abcdef';leaf.content.en.text='Selected product';expect(validResolvedTree(next,out,'en')).toBe(true);leaf.settings={desktop:{align:'end'}};expect(validResolvedTree(next,out,'en')).toBe(false);leaf.settings={};leaf.content.ar={text:'private unrelated change'};expect(validResolvedTree(next,out,'en')).toBe(false);});
 it('empty removes template, no static fallback; rejects extra nodes and over-limit results',()=>{const {tree,id}=fixture();const next=changeRepeat(tree,id,'en',plan),empty=structuredClone(tree);empty.children![0].children![0].children=[];expect(validResolvedTree(next,empty,'en')).toBe(true);expect(validResolvedTree(next,tree,'en')).toBe(false);const many=structuredClone(tree),leaf=many.children![0].children![0].children![0];many.children![0].children![0].children=Array.from({length:9},(_,i)=>({...structuredClone(leaf),id:'n_'+i.toString(16).padStart(16,'0')}));expect(validResolvedTree(next,many,'en')).toBe(false);});
});
