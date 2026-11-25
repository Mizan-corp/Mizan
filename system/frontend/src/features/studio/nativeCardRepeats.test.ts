import {describe,it,expect} from 'vitest';
import {changeCardRepeat,cardRepeatProblem,cardSlotProblem,repeatCardSchema,repeatSchema,validResolvedTree,hasBindings,type NativeCardSlots,type NativeCardRepeatPlan} from './nativeBindings';
import {assertNativeTree,nativeUndo} from './nativeTree';
import {nativeProjectionMap} from './nativeProjectionMap';
import {newPagePayload} from './newPage';
import type {PageNode} from './pagetree';

const slots:NativeCardSlots={heading:'name',text:'price',image:'image'};
const plan:NativeCardRepeatPlan={module:'inventory',source:'products',limit:3,on_missing:'hide'};
const IMG='/uploads/t/00000000-0000-4000-8000-000000000000/product_image/a.png';

// tree: section > columns (row) > column (template) > heading/text/image
function fixture(){
 const tree=newPagePayload({title:'Static',slug:'static',language:'en'}).tree;
 const row=tree.children![0];
 const column=row.children![0];
 const heading=column.children![0];
 const price:PageNode={id:'n_price0',type:'text',settings:{},content:{en:{html:'<p>Price</p>'}}};
 const image:PageNode={id:'n_img000',type:'image',settings:{},content:{en:{src:'/uploads/t/00000000-0000-4000-8000-000000000000/product_image/b.png',alt:'alt'}}};
 column.children=[heading,price,image];
 return {tree,row,column,heading};
}
function clone(column:PageNode,id:string,name:string,price:string|null,src:string|null):PageNode{
 // Backend derives n_<16 lowercase hex> ids for the clone and each kept child.
 const child=(i:number)=>`n_${id.slice(3,18).padEnd(15,'0')}${i.toString(16)}`;
 const out:PageNode={id,type:'column',settings:structuredClone(column.settings),content:{},children:[]};
 const kids=column.children!;
 out.children!.push({...structuredClone(kids[0]),id:child(1),content:{en:{text:name}}});
 if(price!==null)out.children!.push({...structuredClone(kids[1]),id:child(2),content:{en:{html:`<p>${price}</p>`}}});
 if(src!==null)out.children!.push({...structuredClone(kids[2]),id:child(3),content:{en:{src,alt:name}}});
 return out;
}

describe('native card repeats (v1)',()=>{
 it('attaches, edits limit, removes; source retained and undo works',()=>{
  const {tree,column}=fixture();
  const next=changeCardRepeat(tree,column.id,'en',slots,plan);
  assertNativeTree(next);
  expect(hasBindings(next)).toBe(true);
  expect(column.repeat).toBeUndefined(); // source untouched
  const attached=next.children![0].children![0];
  expect(attached.repeat).toEqual({schema:repeatCardSchema,slots,content:{en:plan}});
  const edited=changeCardRepeat(next,column.id,'en',slots,{...plan,limit:5});
  expect(edited.children![0].children![0].repeat?.schema===repeatCardSchema&&edited.children![0].children![0].repeat?.content.en?.limit).toBe(5);
  expect(changeCardRepeat(edited,column.id,'en',slots,null)).toEqual(tree);
  expect(nativeUndo({tree:next,past:[tree],future:[]}).tree).toEqual(tree);
 });
 it('refuses malformed envelopes, slot mismatches and wrong node kinds',()=>{
  for(const v of [
   {schema:repeatCardSchema,content:{en:plan}}, // no slots
   {schema:repeatCardSchema,slots:{text:'price'},content:{en:plan}}, // heading required
   {schema:repeatCardSchema,slots:{...slots,gallery:'image'},content:{en:plan}}, // unknown slot
   {schema:repeatCardSchema,slots,content:{en:{...plan,field:'name'}}}, // v0 field key refused
   {schema:repeatCardSchema,slots,content:{en:{...plan,limit:25}}},
   {schema:repeatCardSchema,slots,content:{en:{...plan,on_missing:'skip'}}},
   {schema:repeatSchema,content:{en:{...plan,field:'name'}}}, // v0 envelope on a column
  ])expect(cardRepeatProblem(v,'column')).toBe(true);
  expect(cardRepeatProblem({schema:repeatCardSchema,slots,content:{en:plan}},'column')).toBe(false);
  expect(cardRepeatProblem({schema:repeatCardSchema,slots,content:{en:plan}},'heading')).toBe(true);
  expect(cardSlotProblem(undefined,slots)).toBe(true);
  expect(cardSlotProblem([{id:'n_h',type:'heading',settings:{},content:{}}],slots)).toBe(true);
  expect(cardSlotProblem([{id:'n_h',type:'heading',settings:{},content:{}}],{heading:'name'})).toBe(false);
  const {tree,column,heading}=fixture();
  expect(()=>changeCardRepeat(tree,heading.id,'en',slots,plan)).toThrow();
  const bound=structuredClone(tree);
  bound.children![0].children![0].children![0].bindings={schema:'mizan.page-bindings.experimental.v0',content:{en:{text:{mode:'dynamic',module:'core',source:'website_profile',field:'display_name',on_missing:'hide'}}}};
  expect(()=>changeCardRepeat(bound,column.id,'en',slots,plan)).toThrow();
  const attached=changeCardRepeat(tree,column.id,'en',slots,plan);
  expect(()=>changeCardRepeat(attached,column.id,'en',{heading:'other',text:'price',image:'image'},plan)).toThrow();
  expect(()=>assertNativeTree(attached)).not.toThrow();
  const badChildren=structuredClone(attached);
  badChildren.children![0].children![0].children!.push({id:'n_btn000',type:'button',settings:{},content:{en:{label:'x',href:'#'}}});
  expect(()=>assertNativeTree(badChildren)).toThrow(); // template children must match slots
 });
 it('accepts exact expanded clones and refuses tampered projections',()=>{
  const {tree,row,column}=fixture();
  const source=changeCardRepeat(tree,column.id,'en',slots,plan);
  const resolved=structuredClone(tree);
  resolved.children![0].children=[
   clone(column,'n_aaaaaaaaaaaaaaa1','Widget','10.00 EGP',IMG),
   clone(column,'n_bbbbbbbbbbbbbbb2','Gadget','25.50 EGP',IMG),
  ];
  expect(validResolvedTree(source,resolved,'en')).toBe(true);
  expect(validResolvedTree(source,tree,'en')).toBe(false); // unresolved template refused
  const tampered=structuredClone(resolved);
  tampered.children![0].children![0].children![1].content.en={html:'<p><b>10.00 EGP</b></p>'};
  expect(validResolvedTree(source,tampered,'en')).toBe(false); // unescaped markup refused
  const settings=structuredClone(resolved);
  settings.children![0].children![0].settings={desktop:{align:'end'}};
  expect(validResolvedTree(source,settings,'en')).toBe(false);
  const extra=structuredClone(resolved);
  (extra.children![0].children![0] as PageNode&{role?:string}).role='admin';
  expect(validResolvedTree(source,extra,'en')).toBe(false);
  const httpsMedia=structuredClone(resolved);
  httpsMedia.children![0].children![0].children![2].content.en={src:'https://cdn.example.com/x.png',alt:'Widget'};
  expect(validResolvedTree(source,httpsMedia,'en')).toBe(true); // https media URL is a valid bounded fill
  const badScheme=structuredClone(resolved);
  badScheme.children![0].children![0].children![2].content.en={src:'javascript:alert(1)',alt:'Widget'};
  expect(validResolvedTree(source,badScheme,'en')).toBe(false);
  const over=structuredClone(resolved);
  over.children![0].children!.push(clone(column,'n_ccccccccccccccc3','Extra','1.00 EGP',IMG),clone(column,'n_ddddddddddddddd4','Extra2','2.00 EGP',IMG));
  expect(validResolvedTree(source,over,'en')).toBe(false); // over plan.limit
  const otherLang=structuredClone(resolved);
  otherLang.children![0].children![0].children![0].content.ar={text:'تغيير'};
  expect(validResolvedTree(source,otherLang,'en')).toBe(false); // untouched languages must match
  expect(row.children!.length).toBe(1); // source untouched
 });
 it('handles dropped slots, empty price and the all-hidden pruned row',()=>{
  const {tree,column}=fixture();
  const source=changeCardRepeat(tree,column.id,'en',slots,plan);
  const dropped=structuredClone(tree);
  dropped.children![0].children=[clone(column,'n_aaaaaaaaaaaaaaa1','NoPrice',null,null)];
  expect(validResolvedTree(source,dropped,'en')).toBe(true); // hidden price/image slots dropped, card kept
  const emptyPlan=changeCardRepeat(tree,column.id,'en',slots,{...plan,on_missing:'empty'});
  const empty=structuredClone(tree);
  empty.children![0].children=[clone(column,'n_aaaaaaaaaaaaaaa1','NoPrice','',null)];
  expect(validResolvedTree(emptyPlan,empty,'en')).toBe(true); // '<p></p>' allowed under empty
  const pruned=structuredClone(tree);
  pruned.children=[];
  expect(validResolvedTree(source,pruned,'en')).toBe(true); // all items hidden: row pruned
  const hollowedOut=structuredClone(tree);
  hollowedOut.children![0].children=[];
  expect(validResolvedTree(source,hollowedOut,'en')).toBe(false); // empty row is not a backend output
 });
 it('maps expanded clones back to the template without changing source',()=>{
  const {tree,column}=fixture();
  const source=changeCardRepeat(tree,column.id,'en',slots,plan);
  const before=JSON.stringify(source);
  const resolved=structuredClone(tree);
  const c1=clone(column,'n_aaaaaaaaaaaaaaa1','Widget','10.00 EGP',IMG),c2=clone(column,'n_bbbbbbbbbbbbbbb2','Gadget',null,null);
  resolved.children![0].children=[c1,c2];
  const map=nativeProjectionMap(source,resolved,'en');
  expect(map[c1.id]).toBe(column.id);
  expect(map[c2.id]).toBe(column.id);
  expect(map[c1.children![0].id]).toBe(column.children![0].id);
  expect(map[c1.children![1].id]).toBe(column.children![1].id);
  expect(map[c1.children![2].id]).toBe(column.children![2].id);
  expect(map[c2.children![0].id]).toBe(column.children![0].id);
  expect(JSON.stringify(source)).toBe(before);
  const bad=structuredClone(resolved);
  bad.children![0].children![0].children![1].content.en={html:'<p><b>10.00 EGP</b></p>'};
  expect(nativeProjectionMap(source,bad,'en')).toEqual({}); // unverified copies are never mapped
 });

 it('expands and validates Arabic content-language projections independently',()=>{
  const {tree,column}=fixture();
  const source=changeCardRepeat(tree,column.id,'ar',slots,plan);
  const attached=source.children![0].children![0];
  expect(attached.repeat).toEqual({schema:repeatCardSchema,slots,content:{ar:plan}});
  const cloneAr=(id:string,name:string,price:string|null):PageNode=>{
   const child=(i:number)=>`n_${id.slice(3,18).padEnd(15,'0')}${i.toString(16)}`;
   const kids=column.children!;
   const out:PageNode={id,type:'column',settings:structuredClone(column.settings),content:{},children:[]};
   out.children!.push({...structuredClone(kids[0]),id:child(1),content:{...structuredClone(kids[0].content),ar:{text:name}}});
   if(price!==null)out.children!.push({...structuredClone(kids[1]),id:child(2),content:{...structuredClone(kids[1].content),ar:{html:`<p>${price}</p>`}}});
   return out;
  };
  const resolved=structuredClone(tree);
  resolved.children![0].children=[
   cloneAr('n_aaaaaaaaaaaaaaa1','ودجت','10.00 جنيه'),
   cloneAr('n_bbbbbbbbbbbbbbb2','جادجت',null),
  ];
  expect(validResolvedTree(source,resolved,'ar')).toBe(true);
  expect(validResolvedTree(source,resolved,'en')).toBe(false); // en projection does not satisfy the ar plan
  const tamperedEn=structuredClone(resolved);
  tamperedEn.children![0].children![0].children![0].content.en={text:'changed'};
  expect(validResolvedTree(source,tamperedEn,'ar')).toBe(false); // untouched languages must match source
  const map=nativeProjectionMap(source,resolved,'ar');
  expect(map['n_aaaaaaaaaaaaaaa1']).toBe(column.id);
  expect(map['n_bbbbbbbbbbbbbbb2']).toBe(column.id);
 });
});
