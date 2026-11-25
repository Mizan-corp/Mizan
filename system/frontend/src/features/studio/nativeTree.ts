import {cardProblem,assertCardScope} from './nativeCards';
import {bindingProblem,itemBindingProblem,itemBindingSchema,repeatProblem,cardRepeatProblem,cardSlotProblem,repeatCardSchema,type NativeCardRepeat} from './nativeBindings';
import type { PageNode } from './pagetree';

export type NativeDevice = 'desktop' | 'tablet' | 'mobile';
export type NativeEdit = { kind: 'content'; id: string; lang: 'en'|'ar'; field: string; value: string } | { kind: 'setting'; id: string; device: NativeDevice; field: string; value: string|number|boolean };
const spacing = ['none','xs','s','m','l','xl'];
const align = ['start','center','end'];
const width = ['auto','full','half','third','two_thirds'];
// Deliberately bounded authoring subset, not the complete platform validator.
const settings: Record<string, Record<string, readonly (string|number|boolean)[]>> = {
  section:{visible:[true,false],padding:spacing,gap:spacing,background:['background','card','primary','dark'],max_width:['narrow','normal','wide','full']},
  columns:{visible:[true,false],columns:[1,2,3,4,5,6],gap:spacing,stack:[true,false],reverse:[true,false]},
  column:{visible:[true,false],width,padding:spacing,align,background:['background','card','primary','dark'],rounded:[true,false]},
  heading:{visible:[true,false],level:[1,2,3,4,5,6],align},
  text:{visible:[true,false],align,variant:['body','eyebrow','note']},
  image:{visible:[true,false],width,rounded:[true,false],art:['none','sculpture','sculpture_alt']},
  button:{visible:[true,false],style:['primary','secondary','ghost'],align},
};
const fields: Record<string, Record<string, number>> = {section:{},columns:{},column:{},heading:{text:200},text:{html:20000},image:{src:2000,alt:300},button:{label:80,href:2000}};
const motion={animation:['none','fade','rise','slide','zoom'],animation_speed:['quick','normal','slow'],animation_delay:['none','short','long']};
for(const schema of Object.values(settings))Object.assign(schema,motion);
export function safeNativeUrl(value: string, image = false): boolean {
  if (!value) return true;
  if (/[\x00-\x20\x7f\\<>"']/.test(value) || value.startsWith('//')) return false;
  if (value.startsWith('/')) return true;
  if (!image && value.startsWith('#')) return true;
  try { const u=new URL(value); return ['http:','https:'].includes(u.protocol) && !u.username && !u.password && (!u.port || ['80','443'].includes(u.port)); } catch { return false; }
}
export function nativeSettingChoices(type: string) { return settings[type] ?? {}; }
export function nativeContentFields(type: string) { return fields[type] ?? {}; }
export function nativeNodes(tree: PageNode): PageNode[] { return [tree,...(tree.children ?? []).flatMap(nativeNodes)]; }

export function assertNativeTree(tree: PageNode): void {
  if (new TextEncoder().encode(JSON.stringify(tree)).length > 200000) throw Error('Tree exceeds the native editor limit.');
  const ids = new Set<string>(); let count=0;
  const visit=(n: PageNode, parent: string|null, depth: number) => {
    if (!n || typeof n !== 'object' || !settings[n.type] || !/^n_[a-z0-9]{4,16}$/.test(n.id) || ids.has(n.id) || ++count > 500 || depth > 12) throw Error('Unsupported node, duplicate ID or tree limit.');
    if(n.bindings!==undefined){const item=n.bindings.schema===itemBindingSchema;if(item?itemBindingProblem(n.bindings,n.type):bindingProblem(n.bindings,n.type))throw Error('Unsupported dynamic binding. Source is protected.');}
    if(n.repeat!==undefined){
      const cardRepeat=n.repeat.schema===repeatCardSchema?(n.repeat as NativeCardRepeat):undefined;
      const problem=cardRepeat?cardRepeatProblem(cardRepeat,n.type)||cardSlotProblem(n.children,cardRepeat.slots)||(n.children??[]).some(c=>c.bindings||c.repeat||c.card):repeatProblem(n.repeat,n.type);
      if(problem||n.bindings)throw Error('Unsupported repeat template.');
    }
    if(n.card!==undefined&&(cardProblem(n.card,n.type)||n.bindings||n.repeat))throw Error('Unsupported product card.');
    ids.add(n.id);
    if (Object.keys(n).some(k=>!['id','type','settings','content','children','bindings','repeat','card'].includes(k))) throw Error('Unsupported node metadata. Source is protected.');
    if (parent === null ? n.type !== 'section' : parent === 'section' ? n.type !== 'columns' : parent === 'columns' ? n.type !== 'column' : parent === 'column' ? ['section','columns','column'].includes(n.type) : true) throw Error('Unsupported composition.');
    if (!n.settings || !n.content || typeof n.settings !== 'object' || typeof n.content !== 'object' || Array.isArray(n.settings) || Array.isArray(n.content)) throw Error('Malformed node fields.');
    for (const [device,values] of Object.entries(n.settings)) {
      if (!['desktop','tablet','mobile'].includes(device) || !values || typeof values!=='object' || Array.isArray(values)) throw Error('Unsupported device settings.');
      for (const [key,value] of Object.entries(values)) if (!settings[n.type][key]?.includes(value)) throw Error('Unsupported setting. Source is protected.');
    }
    for (const [lang,values] of Object.entries(n.content)) {
      if (!['en','ar'].includes(lang) || !values || typeof values!=='object' || Array.isArray(values)) throw Error('Unsupported language content.');
      for (const [key,value] of Object.entries(values)) {
        if (!(key in fields[n.type]) || typeof value!=='string' || value.length > fields[n.type][key]) throw Error('Unsupported content field.');
        if ((key==='src'||key==='href') && !safeNativeUrl(value,key==='src')) throw Error('Unsupported URL.');
      }
    }
    if (n.children !== undefined && !Array.isArray(n.children)) throw Error('Malformed children.');
    if (!['section','columns','column'].includes(n.type) && n.children?.length) throw Error('Leaf node has children.');
    if (n.type==='columns' && ((n.children?.length ?? 0)<1 || (n.children?.length ?? 0)>6)) throw Error('A row needs one to six columns.');
    for(const child of n.children ?? []) visit(child,n.type,depth+1);
  };
  visit(tree,null,0);
  assertCardScope(tree);
  const repeated=nativeNodes(tree).filter(n=>n.repeat);if(repeated.length>1)throw Error('Only one bounded repeat template is supported.');
}
export function editNativeTree(tree: PageNode, edit: NativeEdit): PageNode {
  assertNativeTree(tree);
  const next=structuredClone(tree), node=nativeNodes(next).find(n=>n.id===edit.id);
  if(!node) throw Error('Node not found.');
  if(edit.kind==='content') {
    if(!['en','ar'].includes(edit.lang) || !(edit.field in fields[node.type]) || edit.value.length>fields[node.type][edit.field]) throw Error('Unsupported content edit.');
    if((edit.field==='src'||edit.field==='href')&&!safeNativeUrl(edit.value,edit.field==='src')) throw Error('Use a safe URL.');
    node.content={...node.content,[edit.lang]:{...node.content[edit.lang],[edit.field]:edit.value}};
  } else {
    if(!['desktop','tablet','mobile'].includes(edit.device)||!settings[node.type][edit.field]?.includes(edit.value)) throw Error('Unsupported setting edit.');
    node.settings={...node.settings,[edit.device]:{...node.settings[edit.device],[edit.field]:edit.value}};
  }
  assertNativeTree(next);return next;
}
export type NativeHistory = { tree: PageNode; past: PageNode[]; future: PageNode[] };
export function nativeChange(state: NativeHistory, edit: NativeEdit): NativeHistory {
  const tree=editNativeTree(state.tree,edit);
  if(JSON.stringify(tree)===JSON.stringify(state.tree))return state;
  return {tree,past:[...state.past.slice(-29),state.tree],future:[]};
}
export function nativeUndo(s: NativeHistory): NativeHistory { const tree=s.past.at(-1);return tree?{tree,past:s.past.slice(0,-1),future:[s.tree,...s.future]}:s; }
export function nativeRedo(s: NativeHistory): NativeHistory { const tree=s.future[0];return tree?{tree,past:[...s.past,s.tree],future:s.future.slice(1)}:s; }

export function nativeTreeKey(value: unknown): string {
  const canonical=(v:unknown):unknown=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b)).map(([k,x])=>[k,canonical(x)])):v;
  return JSON.stringify(canonical(value));
}
