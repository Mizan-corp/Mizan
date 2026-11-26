import {describe,it,expect} from 'vitest';
import {bindingProblem,itemBindingProblem,changeBinding,changeItemBinding,hasBindings,validResolvedTree,bindingSchema,itemBindingSchema,cardSlotProblem,type NativeBinding,type NativeItemBinding} from './nativeBindings';
import {assertNativeTree,nativeChange,nativeUndo,type NativeHistory} from './nativeTree';
import {newPagePayload} from './newPage';
const binding:NativeBinding={mode:'dynamic',module:'site',source:'appearance',field:'brand',on_missing:'hide'};
describe('native dynamic binding',()=>{
 it('preserves static fields, languages and source identity; static restores source',()=>{const tree=newPagePayload({title:'Static',slug:'static',language:'en'}).tree;const id=tree.children![0].children![0].children![0].id;const before=structuredClone(tree);const dynamic=changeBinding(tree,id,'en',binding);assertNativeTree(dynamic);expect(hasBindings(dynamic)).toBe(true);expect(tree).toEqual(before);const back=changeBinding(dynamic,id,'en',null);expect(back).toEqual(tree);});
 it('refuses unknown envelope/target/expressions',()=>{for(const value of [{en:{text:binding}},{schema:'unknown',content:{en:{text:binding}}},{schema:bindingSchema,content:{en:{text:{...binding,sql:'bad'}}}},{schema:bindingSchema,content:{en:{text:{...binding,module:'https://external.invalid'}}}}])expect(bindingProblem(value,'heading')).toBe(true);expect(bindingProblem({schema:bindingSchema,content:{en:{text:binding}}},'image')).toBe(true);});
 it('undo retains source binding and static data',()=>{const tree=newPagePayload({title:'Static',slug:'static',language:'en'}).tree;const id=tree.children![0].children![0].children![0].id;const dynamic=changeBinding(tree,id,'en',binding);const s:NativeHistory={tree:dynamic,past:[tree],future:[]};expect(nativeUndo(s).tree).toEqual(tree);const setting=nativeChange(s,{kind:'setting',id,device:'desktop',field:'align',value:'center'});expect(hasBindings(setting.tree)).toBe(true);});
 it('refuses replacement preview content and settings while allowing exact bound hide',()=>{const tree=newPagePayload({title:'Static',slug:'static',language:'en'}).tree;const id=tree.children![0].children![0].children![0].id;const dynamic=changeBinding(tree,id,'en',binding);const resolved=structuredClone(tree);resolved.children![0].children![0].children![0].content.en.text='Brand';expect(validResolvedTree(dynamic,resolved,'en')).toBe(true);resolved.settings={desktop:{padding:'xl'}};expect(validResolvedTree(dynamic,resolved,'en')).toBe(false);const hidden=structuredClone(tree);hidden.children![0].children![0].children=[];expect(validResolvedTree(dynamic,hidden,'en')).toBe(true);expect(validResolvedTree(tree,hidden,'en')).toBe(false);});

});

describe('individually bound elements (v1 envelope)',()=>{
 const item:NativeItemBinding={mode:'dynamic',module:'inventory',source:'products',item_key:'b2c075bd-43bd-5924-a645-d53079717d60',field:'name',on_missing:'hide'};
 const leaf=(id:string,type:string,content:Record<string,Record<string,unknown>>)=>({id,type,settings:{},content});
 const itemTree=()=>({id:'n_0000000000000001',type:'section',settings:{},content:{},children:[{id:'n_0000000000000002',type:'columns',settings:{desktop:{columns:1}},content:{},children:[{id:'n_0000000000000003',type:'column',settings:{},content:{},children:[leaf('n_0000000000000004','heading',{en:{text:'Static heading'}}),leaf('n_0000000000000005','text',{en:{html:'<p>Static text</p>'}}),leaf('n_0000000000000006','image',{en:{alt:''}})]}]}]});
 it('binds and restores each target element per language',()=>{const tree=itemTree();const [heading,text,image]=tree.children[0].children[0].children as Parameters<typeof changeItemBinding>[0][];
  for(const node of [heading,text,image]){const b=node.type==='image'?{...item,field:'image' as const}:item;const before=structuredClone(tree);const bound=changeItemBinding(tree,node.id,'en',b);assertNativeTree(bound);expect(hasBindings(bound)).toBe(true);expect(tree).toEqual(before);const back=changeItemBinding(bound,node.id,'en',null);expect(back).toEqual(tree);}
  // price only on text, image only on image
  expect(()=>changeItemBinding(tree,heading.id,'en',{...item,field:'price'})).toThrow();
  expect(()=>changeItemBinding(tree,text.id,'en',{...item,field:'image'})).toThrow();
  expect(()=>changeItemBinding(tree,image.id,'en',{...item,field:'price'})).toThrow();});
 it('refuses hostile envelopes and identities',()=>{for(const value of [{en:{text:item}},{schema:'unknown',content:{en:{text:item}}},{schema:itemBindingSchema,content:{en:{text:{...item,item_key:'x; drop table'}}}},{schema:itemBindingSchema,content:{en:{text:{...item,field:'price'}}}},{schema:itemBindingSchema,content:{en:{html:item}}},{schema:itemBindingSchema,content:{en:{text:{...item,extra:1}}}}])expect(itemBindingProblem(value,'heading')).toBe(true);
  expect(itemBindingProblem({schema:itemBindingSchema,content:{en:{text:item}}},'button')).toBe(true);
  expect(itemBindingProblem({schema:itemBindingSchema,content:{en:{text:item},ar:{text:item}}},'heading')).toBe(false);
  expect(itemBindingProblem({schema:itemBindingSchema,content:{en:{html:{...item,field:'price'}}}},'text')).toBe(false);
  expect(itemBindingProblem({schema:itemBindingSchema,content:{en:{src:{...item,field:'image'}}}},'image')).toBe(false);});
 it('never mixes with the v0 scalar envelope on one node',()=>{const tree=itemTree();const heading=tree.children[0].children[0].children![0];
  const v0=changeBinding(tree,heading.id,'en',{mode:'dynamic',module:'site',source:'appearance',field:'brand',on_missing:'hide'});
  expect(()=>changeItemBinding(v0,heading.id,'en',item)).toThrow();
  const v1=changeItemBinding(tree,heading.id,'en',item);
  expect(()=>changeBinding(v1,heading.id,'en',{mode:'dynamic',module:'site',source:'appearance',field:'brand',on_missing:'hide'})).toThrow();});
 it('resolved projection allows exact fills and bound hides only',()=>{const tree=itemTree();const heading=tree.children[0].children[0].children![0];
  const bound=changeItemBinding(tree,heading.id,'en',item);
  const resolved=structuredClone(tree);resolved.children[0].children[0].children![0].content.en.text='Fixture Card Widget';
  expect(validResolvedTree(bound,resolved,'en')).toBe(true);
  const hidden=structuredClone(tree);hidden.children[0].children[0].children=hidden.children[0].children[0].children!.filter(c=>c.type!=='heading');
  expect(validResolvedTree(bound,hidden,'en')).toBe(true);
  const replaced=structuredClone(resolved);replaced.children[0].children[0].children![0].settings={desktop:{align:'center'}};
  expect(validResolvedTree(bound,replaced,'en')).toBe(false);});
});

describe('card repeat multi-text slots',()=>{
 const kids=(types:string[])=>types.map((t,i)=>({id:`n_${String(i).padStart(16,'0')}`,type:t,settings:{},content:{}}) as never);
 it('binds successive text children to text, text2, text3 in order',()=>{
  expect(cardSlotProblem(kids(['heading','text','text']),{heading:'name',text:'description',text2:'starting_price'})).toBe(false);
  expect(cardSlotProblem(kids(['heading','text','text','text']),{heading:'name',text:'a',text2:'b',text3:'c'})).toBe(false);
  expect(cardSlotProblem(kids(['heading','text']),{heading:'name',text:'price'})).toBe(false);
 });
 it('rejects missing, extra or unknown slot coverage',()=>{
  expect(cardSlotProblem(kids(['heading','text','text']),{heading:'name',text:'description'})).toBe(true);
  expect(cardSlotProblem(kids(['heading','text']),{heading:'name',text:'a',text2:'b'})).toBe(true);
  expect(cardSlotProblem(kids(['heading','text','image']),{heading:'name',text:'a'})).toBe(true);
 });
});
