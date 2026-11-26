import {validResolvedCards} from './nativeCards';
import type {PageNode} from './pagetree';
export const bindingSchema='mizan.page-bindings.experimental.v0';
export type NativeBinding={mode:'dynamic';module:string;source:string;field:string;on_missing:'hide'|'empty'};
export type NativeBindings={schema:typeof bindingSchema;content:Partial<Record<'en'|'ar',{text:NativeBinding}>>};
export function bindingProblem(value:unknown,type:string):boolean{
 if(!value||typeof value!=='object'||Array.isArray(value))return true;
 const x=value as NativeBindings;
 if(Object.keys(x).sort().join()!=='content,schema'||x.schema!==bindingSchema||type!=='heading'||!x.content||typeof x.content!=='object'||Array.isArray(x.content)||!Object.keys(x.content).length)return true;
 return Object.entries(x.content).some(([lang,f])=>!['en','ar'].includes(lang)||!f||Object.keys(f).join()!=='text'||!f.text||Object.keys(f.text).sort().join()!=='field,mode,module,on_missing,source'||f.text.mode!=='dynamic'||!['hide','empty'].includes(f.text.on_missing)||!Object.entries({module:f.text.module,source:f.text.source,field:f.text.field}).every(([k,v])=>typeof v==='string'&&(k==='module'?/^[a-z][a-z0-9_]{0,47}(\.[a-z][a-z0-9_]{0,47})?$/:/^[a-z][a-z0-9_]{0,47}$/).test(v)));
}
export const itemBindingSchema='mizan.page-bindings.experimental.v1';
export type NativeItemBinding={mode:'dynamic';module:string;source:string;item_key:string;field:'name'|'price'|'image'|'description';on_missing:'hide'|'empty'};
export type NativeItemBindings={schema:typeof itemBindingSchema;content:Partial<Record<'en'|'ar',Record<string,NativeItemBinding>>>};
// Which content field each node type may bind to a consented record, and which
// provider fields may fill it. Mirrors the platform manifest allowlist.
export const itemBindingTargets:Record<string,Record<string,ReadonlyArray<NativeItemBinding['field']>>>={heading:{text:['name']},text:{html:['name','price','description']},image:{src:['image']}};
// v2 route mode ("current item"): the visitor URL's item segment selects the
// record, so the declaration carries no pinned item_key. Mirrors the manifest.
export const itemRouteBindingSchema='mizan.page-bindings.experimental.v2';
export type NativeRouteItemBinding={mode:'route';module:string;source:string;field:'name'|'price'|'image'|'description';on_missing:'hide'|'empty'};
export type NativeRouteItemBindings={schema:typeof itemRouteBindingSchema;content:Partial<Record<'en'|'ar',Record<string,NativeRouteItemBinding>>>};
export const itemRouteBindingTargets=itemBindingTargets;
export function itemRouteBindingProblem(value:unknown,type:string):boolean{
 if(!value||typeof value!=='object'||Array.isArray(value))return true;
 const x=value as NativeRouteItemBindings;
 if(Object.keys(x).sort().join()!=='content,schema'||x.schema!==itemRouteBindingSchema||!x.content||typeof x.content!=='object'||Array.isArray(x.content)||!Object.keys(x.content).length)return true;
 const target=itemRouteBindingTargets[type];if(!target)return true;
 return Object.entries(x.content).some(([lang,f])=>!['en','ar'].includes(lang)||!f||typeof f!=='object'||Array.isArray(f)||Object.keys(f).join()!==Object.keys(target).join()||Object.entries(f).some(([field,b])=>!b||Object.keys(b).sort().join()!=='field,mode,module,on_missing,source'||b.mode!=='route'||!['hide','empty'].includes(b.on_missing)||!target[field].includes(b.field)||!Object.entries({module:b.module,source:b.source}).every(([k,v])=>typeof v==='string'&&(k==='module'?/^[a-z][a-z0-9_]{0,47}(\.[a-z][a-z0-9_]{0,47})?$/:/^[a-z][a-z0-9_]{0,47}$/).test(v))));
}
export function itemBindingProblem(value:unknown,type:string):boolean{
 if(!value||typeof value!=='object'||Array.isArray(value))return true;
 const x=value as NativeItemBindings;
 if(Object.keys(x).sort().join()!=='content,schema'||x.schema!==itemBindingSchema||!x.content||typeof x.content!=='object'||Array.isArray(x.content)||!Object.keys(x.content).length)return true;
 const target=itemBindingTargets[type];if(!target)return true;
 return Object.entries(x.content).some(([lang,f])=>!['en','ar'].includes(lang)||!f||typeof f!=='object'||Array.isArray(f)||Object.keys(f).join()!==Object.keys(target).join()||Object.entries(f).some(([field,b])=>!b||Object.keys(b).sort().join()!=='field,item_key,mode,module,on_missing,source'||b.mode!=='dynamic'||!['hide','empty'].includes(b.on_missing)||!target[field].includes(b.field)||!/^[A-Za-z0-9_-]{1,64}$/.test(b.item_key)||!Object.entries({module:b.module,source:b.source}).every(([k,v])=>typeof v==='string'&&(k==='module'?/^[a-z][a-z0-9_]{0,47}(\.[a-z][a-z0-9_]{0,47})?$/:/^[a-z][a-z0-9_]{0,47}$/).test(v))));
}
export function changeItemBinding(tree:PageNode,id:string,language:'en'|'ar',binding:NativeItemBinding|NativeRouteItemBinding|null):PageNode{
 const next=structuredClone(tree);const visit=(n:PageNode):boolean=>{if(n.id===id){
  const target=itemBindingTargets[n.type];if(!target||n.repeat||n.card)throw Error('Remove collection or cards before item binding.');
  const field=Object.keys(target)[0];
  const schema=binding?.mode==='route'?itemRouteBindingSchema:itemBindingSchema;
  if(n.bindings&&n.bindings.schema!==itemBindingSchema&&n.bindings.schema!==itemRouteBindingSchema)throw Error('Remove the existing binding first.');
  if(n.bindings&&binding&&n.bindings.schema!==schema)throw Error('Remove the existing binding first.');
  if(n.bindings&&!binding&&n.bindings.schema!==itemBindingSchema&&n.bindings.schema!==itemRouteBindingSchema)throw Error('Remove the existing binding first.');
  if(binding&&!target[field].includes(binding.field))throw Error('Field not bindable to this element.');
  const content:Partial<Record<'en'|'ar',Record<string,NativeItemBinding|NativeRouteItemBinding>>>={...((n.bindings?.schema===itemBindingSchema||n.bindings?.schema===itemRouteBindingSchema)?(n.bindings as NativeItemBindings|NativeRouteItemBindings).content:{})} as Partial<Record<'en'|'ar',Record<string,NativeItemBinding|NativeRouteItemBinding>>>;
  if(binding)content[language]={[field]:structuredClone(binding)};else delete content[language];
  if(Object.keys(content).length)n.bindings={schema,content} as NativeItemBindings|NativeRouteItemBindings;else delete n.bindings;return true;}return(n.children??[]).some(visit);};
 if(!visit(next))throw Error('Element not found.');return next;
}
export function hasBindings(tree:PageNode):boolean{return !!tree.bindings||!!tree.repeat||!!tree.card||(tree.children??[]).some(hasBindings);}
export function changeBinding(tree:PageNode,id:string,language:'en'|'ar',binding:NativeBinding|null):PageNode{
 const next=structuredClone(tree);const visit=(n:PageNode):boolean=>{if(n.id===id){if(n.type!=='heading'||n.repeat)throw Error('Remove collection before scalar binding.');if(n.bindings&&n.bindings.schema!==bindingSchema)throw Error('Remove the existing binding first.');const content:Partial<Record<'en'|'ar',{text:NativeBinding}>>={...(n.bindings?.schema===bindingSchema?(n.bindings as NativeBindings).content:{})};if(binding)content[language]={text:structuredClone(binding)};else delete content[language];if(Object.keys(content).length)n.bindings={schema:bindingSchema,content};else delete n.bindings;return true;}return(n.children??[]).some(visit);};
 if(!visit(next))throw Error('Heading not found.');return next;
}
const sameJson=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b);
function safeRepeatMedia(value:string):boolean{
 if(/[\x00-\x20\x7f\\<>"']/.test(value)||value.startsWith('//'))return false;
 if(value.startsWith('/'))return true;
 try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&(!u.port||['80','443'].includes(u.port));}catch{return false}
}
/** Row carrying an active v1 card template; the backend prunes it when every item is hidden. */
function containsCardRepeat(node:PageNode,language:'en'|'ar'):boolean{
 return ((node.repeat?.schema===repeatCardSchema||node.repeat?.schema===repeatCategorySchema)&&!!node.repeat.content[language])||(node.children??[]).some(c=>containsCardRepeat(c,language));
}
/** One expanded v1 card: the template column with derived ids and bounded typed fills only. */
function validCardClone(template:PageNode,clone:PageNode,language:'en'|'ar'):boolean{
 if(clone.type!=='column'||!sameJson(template.settings,clone.settings)||!sameJson(template.content,clone.content))return false;
 if(Object.keys(clone).some(k=>!['id','type','settings','content','children'].includes(k)))return false;
 const tKids=template.children??[],cKids=clone.children??[];
 if(!cKids.length||cKids.length>tKids.length)return false;
 let cursor=0;
 for(const c of cKids){
  let t=cursor;while(t<tKids.length&&tKids[t].type!==c.type)t++;
  if(t>=tKids.length)return false;
  const tmpl=tKids[t];cursor=t+1;
  if(Object.keys(c).some(k=>!['id','type','settings','content','children'].includes(k)))return false;
  if(!/^n_[a-f0-9]{16}$/.test(c.id)||!sameJson(tmpl.settings,c.settings)||c.children?.length)return false;
  const expected=structuredClone(tmpl.content);
  if(c.type==='heading'){const text=c.content?.[language]?.text;if(typeof text!=='string'||text.length>200)return false;expected[language]={...expected[language],text};}
  else if(c.type==='text'){const html=c.content?.[language]?.html;if(typeof html!=='string'||html.length>20000||!/^<p>(?:[^&<>]|&(amp|lt|gt|quot|#x27);)*<\/p>$/.test(html))return false;expected[language]={...expected[language],html};}
  else if(c.type==='image'){const v=c.content?.[language];const src=v?.src,alt=v?.alt;if(typeof src!=='string'||!src.length||src.length>2000||!safeRepeatMedia(src)||typeof alt!=='string'||alt.length>300)return false;expected[language]={src,alt};}
  else return false;
  if(!sameJson(expected,c.content))return false;
 }
 return true;
}
/** Trust only an exact structural projection, never a replacement page from preview. */
function validResolvedScalars(source:PageNode,resolved:PageNode,language:'en'|'ar'):boolean{
 const same=sameJson;
 const visit=(a:PageNode,b:PageNode):boolean=>{
  if(!b||a.id!==b.id||a.type!==b.type||b.bindings||b.repeat||!same(a.settings,b.settings))return false;
  if(Object.keys(b).some(k=>!['id','type','settings','content','children'].includes(k)))return false;
  const boundFields=(a.bindings?.content as Record<string,Record<string,{on_missing:string}>>|undefined)?.[language];
  const expected=structuredClone(a.content);
  if(boundFields)for(const field of Object.keys(boundFields)){
   const value=b.content[language]?.[field];
   if(field==='text'){if(typeof value!=='string'||value.length>200)return false;}
   else if(field==='html'){if(typeof value!=='string'||value.length>20000||!/^<p>(?:[^&<>]|&(amp|lt|gt|quot|#x27);)*<\/p>$/.test(value))return false;}
   else if(field==='src'){if(typeof value!=='string'||!safeRepeatMedia(value))return false;}
   else return false;
   expected[language]={...expected[language],[field]:value};
  }
  if(!same(expected,b.content))return false;
  const kids=b.children??[],original=a.children??[];let index=0;
  for(const [originalIndex,child] of original.entries()){
   const cardRepeat=(child.repeat?.schema===repeatCardSchema||child.repeat?.schema===repeatCategorySchema)?child.repeat:undefined;
   if(cardRepeat?.content[language]){let count=0;while(index<kids.length&&kids[index].id!==original[originalIndex+1]?.id&&/^n_[a-f0-9]{16}$/.test(kids[index].id)&&kids[index].id!==child.id){if(++count>cardRepeat.content[language]!.limit||!validCardClone(child,kids[index],language))return false;index++;}if(!count&&original.length===1)return false;continue;}
   const repeat=child.repeat?.schema===repeatSchema?child.repeat?.content[language]:undefined;
   if(repeat){let count=0;while(index<kids.length&&kids[index].id!==original[originalIndex+1]?.id&&/^n_[a-f0-9]{16}$/.test(kids[index].id)&&kids[index].id!==child.id){const generated=kids[index];const value=generated.content?.[language]?.text;if(typeof value!=='string'||value.length>200||++count>repeat.limit)return false;const expected=structuredClone(child);delete expected.repeat;expected.id=generated.id;expected.content[language]={...expected.content[language],text:value};if(!same(expected,generated))return false;index++;}continue;}
   if(kids[index]?.id===child.id){if(!visit(child,kids[index++]))return false;}else if(Object.values(((child.bindings?.content as Record<string,Record<string,{on_missing:string}>>|undefined)?.[language])??{}).some(b=>b.on_missing==='hide')){continue;}else if(containsCardRepeat(child,language)){
    // A repeat that overflows its row is split by the server into sibling rows cloned from this row (derived ids, same type and settings). Rejoin them so the row validates as one.
    const stop=original[originalIndex+1]?.id,group:PageNode[]=[];
    while(index<kids.length&&kids[index].id!==stop&&/^n_[a-f0-9]{16}$/.test(kids[index].id)&&kids[index].type===child.type&&same(kids[index].settings,child.settings))group.push(kids[index++]);
    if(group.length){const merged:PageNode={...group[0],id:child.id,children:group.flatMap(g=>g.children??[])};if(!visit(child,merged))return false;}
   }else return false;
  }
  return index===kids.length;
 };
 try{return visit(source,resolved)}catch{return false}
}
export const repeatSchema='mizan.page-repeat.experimental.v0';
export type NativeRepeatPlan={module:string;source:string;field:string;limit:number;on_missing:'hide'|'empty'};
export type NativeRepeat={schema:typeof repeatSchema;content:Partial<Record<'en'|'ar',NativeRepeatPlan>>};
export const repeatCardSchema='mizan.page-repeat.experimental.v1';
export const repeatCategorySchema='mizan.page-repeat.experimental.v2';
export type NativeCardSlots={heading:string;text?:string;text2?:string;text3?:string;image?:string};
export type NativeCardRepeatPlan={module:string;source:string;limit:number;on_missing:'hide'|'empty'};
export type NativeCategoryRepeatPlan={module:string;source:string;category:'route';limit:number;on_missing:'hide'|'empty'};
export type NativeCardRepeat={schema:typeof repeatCardSchema|typeof repeatCategorySchema;slots:NativeCardSlots;content:Partial<Record<'en'|'ar',NativeCardRepeatPlan|NativeCategoryRepeatPlan>>};
export function cardRepeatProblem(value:unknown,type:string):boolean{
 if(!value||typeof value!=='object'||Array.isArray(value))return true;const v=value as NativeCardRepeat;
 if(type!=='column'||Object.keys(v).sort().join()!=='content,schema,slots'||(v.schema!==repeatCardSchema&&v.schema!==repeatCategorySchema))return true;
 const slots=v.slots;if(!slots||typeof slots!=='object'||Array.isArray(slots))return true;
 const keys=Object.keys(slots);
 if(!keys.includes('heading')||keys.some(k=>!['heading','text','text2','text3','image'].includes(k)))return true;
 if(!Object.values(slots).every(s=>typeof s==='string'&&/^[a-z][a-z0-9_]{0,47}$/.test(s)))return true;
 if(!v.content||typeof v.content!=='object'||Array.isArray(v.content)||!Object.keys(v.content).length)return true;
 const planKeys=v.schema===repeatCategorySchema?'category,limit,module,on_missing,source':'limit,module,on_missing,source';
 return Object.entries(v.content).some(([lang,p])=>!['en','ar'].includes(lang)||!p||Object.keys(p).sort().join()!==planKeys||(v.schema===repeatCategorySchema&&(p as NativeCategoryRepeatPlan).category!=='route')||!Number.isInteger(p.limit)||p.limit<1||p.limit>24||!['hide','empty'].includes(p.on_missing)||![p.module,p.source].every(s=>typeof s==='string'&&/^[a-z][a-z0-9_]{0,47}$/.test(s)));
}
/** Template column children must match the declared typed slots exactly. */
export function cardSlotProblem(children:PageNode[]|undefined,slots:NativeCardSlots):boolean{
 const kinds=(children??[]).map(c=>c.type);
 if(!kinds.length||kinds.length!==Object.keys(slots).length||!kinds.includes('heading'))return true;
 // Successive text children bind to the ordered text slots: text, text2, text3.
 const textSlots=(['text','text2','text3'] as const).filter(k=>slots[k]!==undefined);let ti=0;
 for(const k of kinds){
  if(k==='heading'){if(!slots.heading)return true;}
  else if(k==='image'){if(!slots.image)return true;}
  else if(k==='text'){if(ti>=textSlots.length)return true;ti++;}
  else return true;
 }
 return ti!==textSlots.length;
}
export function sameCardSlots(a:NativeCardSlots,b:NativeCardSlots):boolean{return a.heading===b.heading&&a.text===b.text&&a.text2===b.text2&&a.text3===b.text3&&a.image===b.image;}
export function changeCardRepeat(tree:PageNode,id:string,language:'en'|'ar',slots:NativeCardSlots,plan:NativeCardRepeatPlan|NativeCategoryRepeatPlan|null):PageNode{
 const next=structuredClone(tree);let found=false;
 const anyCard=(n:PageNode):boolean=>!!n.card||(n.children??[]).some(anyCard);
 if(plan&&anyCard(next))throw Error('Remove product cards before collection repeats.');
 const visit=(n:PageNode):void=>{
  if(n.id===id){found=true;
   if(n.type!=='column')throw Error('Only column card templates supported.');
   if(n.bindings||n.card)throw Error('Remove other data connections first.');
   if(cardSlotProblem(n.children,slots))throw Error('Column children must match the card slots.');
   if((n.children??[]).some(c=>c.bindings||c.repeat||c.card))throw Error('Remove data connections inside the column first.');
   const schema=plan&&'category' in plan?repeatCategorySchema:repeatCardSchema;
   if(n.repeat){
    if(n.repeat.schema!==repeatCardSchema&&n.repeat.schema!==repeatCategorySchema)throw Error('Remove the existing repeat first.');
    if(plan&&n.repeat.schema!==schema)throw Error('Remove the existing repeat first.');
    if(!sameCardSlots(n.repeat.slots,slots))throw Error('Card slots stay fixed while a repeat is attached.');
   }
   const content:Partial<Record<'en'|'ar',NativeCardRepeatPlan|NativeCategoryRepeatPlan>>={...n.repeat?.content};if(plan)content[language]=structuredClone(plan);else delete content[language];
   if(Object.keys(content).length)n.repeat={schema,slots:structuredClone(slots),content};else delete n.repeat;return;
  }
  for(const c of n.children??[])visit(c);
 };
 visit(next);if(!found)throw Error('Template missing.');return next;
}
export function repeatProblem(value:unknown,type:string):boolean{
 if(!value||typeof value!=='object'||Array.isArray(value))return true;const v=value as NativeRepeat;
 if(type!=='heading'||Object.keys(v).sort().join()!=='content,schema'||v.schema!==repeatSchema||!v.content||typeof v.content!=='object'||Array.isArray(v.content)||!Object.keys(v.content).length)return true;
 return Object.entries(v.content).some(([lang,p])=>!['en','ar'].includes(lang)||!p||Object.keys(p).sort().join()!=='field,limit,module,on_missing,source'||!Number.isInteger(p.limit)||p.limit<1||p.limit>24||!['hide','empty'].includes(p.on_missing)||![p.module,p.source,p.field].every(s=>typeof s==='string'&&/^[a-z][a-z0-9_]{0,47}$/.test(s)));
}
export function changeRepeat(tree:PageNode,id:string,language:'en'|'ar',plan:NativeRepeatPlan|null):PageNode{
 const next=structuredClone(tree);let found=false;const visit=(n:PageNode)=>{if(n.id===id){found=true;if(n.type!=='heading')throw Error('Only heading templates supported.');if(n.bindings)throw Error('Remove scalar binding first.');if(n.repeat&&n.repeat.schema!==repeatSchema)throw Error('Remove the card repeat first.');const content:Partial<Record<'en'|'ar',NativeRepeatPlan>>={...n.repeat?.content};if(plan)content[language]=structuredClone(plan);else delete content[language];if(Object.keys(content).length)n.repeat={schema:repeatSchema,content};else delete n.repeat;}for(const c of n.children??[])visit(c)};visit(next);if(!found)throw Error('Template missing.');return next;
}

export function validResolvedTree(source:PageNode,resolved:PageNode,language:'en'|'ar'):boolean{return validResolvedCards(source,resolved,language,validResolvedScalars);}
