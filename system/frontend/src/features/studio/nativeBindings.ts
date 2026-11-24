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
export function hasBindings(tree:PageNode):boolean{return !!tree.bindings||!!tree.repeat||(tree.children??[]).some(hasBindings);}
export function changeBinding(tree:PageNode,id:string,language:'en'|'ar',binding:NativeBinding|null):PageNode{
 const next=structuredClone(tree);const visit=(n:PageNode):boolean=>{if(n.id===id){if(n.type!=='heading'||n.repeat)throw Error('Remove collection before scalar binding.');const content={...n.bindings?.content};if(binding)content[language]={text:structuredClone(binding)};else delete content[language];if(Object.keys(content).length)n.bindings={schema:bindingSchema,content};else delete n.bindings;return true;}return(n.children??[]).some(visit);};
 if(!visit(next))throw Error('Heading not found.');return next;
}
/** Trust only an exact structural projection, never a replacement page from preview. */
export function validResolvedTree(source:PageNode,resolved:PageNode,language:'en'|'ar'):boolean{
 const same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b);
 const visit=(a:PageNode,b:PageNode):boolean=>{
  if(!b||a.id!==b.id||a.type!==b.type||b.bindings||b.repeat||!same(a.settings,b.settings))return false;
  if(Object.keys(b).some(k=>!['id','type','settings','content','children'].includes(k)))return false;
  const bound=a.bindings?.content[language]?.text;
  const expected=structuredClone(a.content);
  if(bound){const value=b.content[language]?.text;if(typeof value!=='string'||value.length>200)return false;expected[language]={...expected[language],text:value};}
  if(!same(expected,b.content))return false;
  const kids=b.children??[],original=a.children??[];let index=0;
  for(const [originalIndex,child] of original.entries()){const repeat=child.repeat?.content[language];if(repeat){let count=0;while(index<kids.length&&kids[index].id!==original[originalIndex+1]?.id&&/^n_[a-f0-9]{16}$/.test(kids[index].id)&&kids[index].id!==child.id){const generated=kids[index];const value=generated.content?.[language]?.text;if(typeof value!=='string'||value.length>200||++count>repeat.limit)return false;const expected=structuredClone(child);delete expected.repeat;expected.id=generated.id;expected.content[language]={...expected.content[language],text:value};if(!same(expected,generated))return false;index++;}continue;}if(kids[index]?.id===child.id){if(!visit(child,kids[index++]))return false;}else if(child.bindings?.content[language]?.text?.on_missing!=='hide')return false;}
  return index===kids.length;
 };
 try{return visit(source,resolved)}catch{return false}
}
export const repeatSchema='mizan.page-repeat.experimental.v0';
export type NativeRepeatPlan={module:string;source:string;field:string;limit:number;on_missing:'hide'|'empty'};
export type NativeRepeat={schema:typeof repeatSchema;content:Partial<Record<'en'|'ar',NativeRepeatPlan>>};
export function repeatProblem(value:unknown,type:string):boolean{
 if(!value||typeof value!=='object'||Array.isArray(value))return true;const v=value as NativeRepeat;
 if(type!=='heading'||Object.keys(v).sort().join()!=='content,schema'||v.schema!==repeatSchema||!v.content||typeof v.content!=='object'||Array.isArray(v.content)||!Object.keys(v.content).length)return true;
 return Object.entries(v.content).some(([lang,p])=>!['en','ar'].includes(lang)||!p||Object.keys(p).sort().join()!=='field,limit,module,on_missing,source'||!Number.isInteger(p.limit)||p.limit<1||p.limit>24||!['hide','empty'].includes(p.on_missing)||![p.module,p.source,p.field].every(s=>typeof s==='string'&&/^[a-z][a-z0-9_]{0,47}$/.test(s)));
}
export function changeRepeat(tree:PageNode,id:string,language:'en'|'ar',plan:NativeRepeatPlan|null):PageNode{
 const next=structuredClone(tree);let found=false;const visit=(n:PageNode)=>{if(n.id===id){found=true;if(n.type!=='heading')throw Error('Only heading templates supported.');if(n.bindings)throw Error('Remove scalar binding first.');const content={...n.repeat?.content};if(plan)content[language]=structuredClone(plan);else delete content[language];if(Object.keys(content).length)n.repeat={schema:repeatSchema,content};else delete n.repeat;}for(const c of n.children??[])visit(c)};visit(next);if(!found)throw Error('Template missing.');return next;
}
