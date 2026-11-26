import {describe,it,expect} from 'vitest';
import {changeItemBinding,changeCardRepeat,itemRouteBindingProblem,cardRepeatProblem,itemRouteBindingSchema,repeatCategorySchema,type NativeRouteItemBinding,type NativeCategoryRepeatPlan} from './nativeBindings';
import {assertNativeTree} from './nativeTree';
const leaf=(id:string,type:string,content:Record<string,Record<string,unknown>>)=>({id,type,settings:{},content});
const tree=()=>({id:'n_0000000000000001',type:'section',settings:{},content:{},children:[{id:'n_0000000000000002',type:'columns',settings:{desktop:{columns:1}},content:{},children:[{id:'n_0000000000000003',type:'column',settings:{},content:{},children:[leaf('n_0000000000000004','heading',{en:{text:'Name'}}),leaf('n_0000000000000005','text',{en:{html:'<p>Text</p>'}}),leaf('n_0000000000000006','image',{en:{alt:''}})]}]}]});
const route:NativeRouteItemBinding={mode:'route',module:'inventory',source:'products',field:'name',on_missing:'hide'};
describe('route item bindings (v2 envelope)',()=>{
 it('binds route mode per element and restores static',()=>{const t=tree();const heading=t.children[0].children[0].children![0];
  const bound=changeItemBinding(t,heading.id,'en',route);assertNativeTree(bound);
  expect(bound.children![0].children![0].children![0].bindings!.schema).toBe(itemRouteBindingSchema);
  expect(changeItemBinding(bound,heading.id,'en',null)).toEqual(t);});
 it('supports description on text elements only',()=>{const t=tree();const [heading,text,image]=t.children[0].children[0].children as {id:string}[];
  assertNativeTree(changeItemBinding(t,text.id,'en',{...route,field:'description'}));
  expect(()=>changeItemBinding(t,heading.id,'en',{...route,field:'description'})).toThrow();
  expect(()=>changeItemBinding(t,image.id,'en',{...route,field:'description'})).toThrow();});
 it('refuses pinned identities and foreign schemas',()=>{
  expect(itemRouteBindingProblem({schema:itemRouteBindingSchema,content:{en:{text:{...route,item_key:'b2c075bd-43bd-5924-a645-d53079717d60'}}}},'heading')).toBe(true);
  expect(itemRouteBindingProblem({schema:itemRouteBindingSchema,content:{en:{text:{...route,mode:'dynamic'}}}},'heading')).toBe(true);
  expect(itemRouteBindingProblem({schema:'mizan.page-bindings.experimental.v1',content:{en:{text:route}}},'heading')).toBe(true);
  expect(itemRouteBindingProblem({schema:itemRouteBindingSchema,content:{en:{text:route},ar:{text:{...route,field:'description'}}}},'heading')).toBe(true);
  expect(itemRouteBindingProblem({schema:itemRouteBindingSchema,content:{en:{html:{...route,field:'price'}}}},'text')).toBe(false);});
 it('never mixes v1 and v2 envelopes on one node',()=>{const t=tree();const heading=t.children[0].children[0].children![0];
  const v2=changeItemBinding(t,heading.id,'en',route);
  expect(()=>changeItemBinding(v2,heading.id,'ar',{mode:'dynamic',module:'inventory',source:'products',item_key:'b2c075bd-43bd-5924-a645-d53079717d60',field:'name',on_missing:'hide'})).toThrow();});
});
describe('route category card repeat (v2)',()=>{
 const slots={heading:'name',text:'price',image:'image'} as const;
 const plan:NativeCategoryRepeatPlan={module:'inventory',source:'category_products',category:'route',limit:8,on_missing:'hide'};
 it('attaches a category repeat to a card-shaped column and validates',()=>{const t=tree();const column=t.children[0].children[0];
  const col=changeCardRepeat(t,column.id,'en',slots,plan);assertNativeTree(col);
  expect(col.children![0].children![0].repeat!.schema).toBe(repeatCategorySchema);
  expect(changeCardRepeat(col,column.id,'en',slots,null)).toEqual(t);});
 it('refuses non-route categories and unknown sources',()=>{
  const v2=(p:unknown)=>({schema:repeatCategorySchema,slots,content:{en:p}});
  expect(cardRepeatProblem(v2({...plan,category:'b2c075bd-43bd-5924-a645-d53079717d60'}),'column')).toBe(true);
  expect(cardRepeatProblem(v2({module:'inventory',source:'category_products',limit:8,on_missing:'hide'}),'column')).toBe(true);
  expect(cardRepeatProblem(v2(plan),'column')).toBe(false);
  expect(cardRepeatProblem(v2(plan),'heading')).toBe(true);});
});
