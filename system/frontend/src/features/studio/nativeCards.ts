import type {PageNode} from './pagetree';
export const cardSchema='mizan.page-card.experimental.v0';
export type CardPlan={module:'inventory';source:'website_cards';limit:number;products?:string[];targets:{name:string;price:string;image:string}};
export type NativeCard={schema:typeof cardSchema;content:Partial<Record<'en'|'ar',CardPlan>>};
const id=(v:unknown)=>typeof v==='string'&&/^n_[a-z0-9]{4,16}$/.test(v);
export function cardProblem(value:unknown,type:string):boolean{
 if(!value||typeof value!=='object'||Array.isArray(value))return true;const v=value as NativeCard;
 if(type!=='column'||Object.keys(v).sort().join()!=='content,schema'||v.schema!==cardSchema||!v.content||Array.isArray(v.content)||!Object.keys(v.content).length||Object.keys(v.content).length>2)return true;
 return Object.entries(v.content).some(([lang,p])=>!['en','ar'].includes(lang)||!p||!['limit,module,source,targets','limit,module,products,source,targets'].includes(Object.keys(p).sort().join())||p.module!=='inventory'||p.source!=='website_cards'||!Number.isInteger(p.limit)||p.limit<1||p.limit>6||('products' in p&&(!Array.isArray(p.products)||p.products.length>6||p.products.some(x=>typeof x!=='string'||!/^([a-f0-9]{8}-)([a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(x))||new Set(p.products).size!==p.products.length))||!p.targets||Object.keys(p.targets).sort().join()!=='image,name,price'||!Object.values(p.targets).every(id)||new Set(Object.values(p.targets)).size!==3);
}
const nodes=(n:PageNode):PageNode[]=>[n,...(n.children??[]).flatMap(nodes)];
export function assertCardScope(tree:PageNode){
 const all=nodes(tree),cards=all.filter(n=>n.card);if(!cards.length)return;
 if(cards.length>4||all.some(n=>n.repeat))throw Error('Use up to four product-card sections, without heading repeats.');
 const totals={en:all.length,ar:all.length},counts={en:0,ar:0};
 for(const t of cards){
  const row=all.find(n=>n.children?.includes(t));if(row?.type!=='columns'||row.children?.length!==1)throw Error('Product card needs its own one-column row.');
  if(nodes(t).some(n=>n.bindings||n.repeat||(n!==t&&n.card)))throw Error('Product-card item scope cannot contain other data bindings.');
  for(const [language,plan] of Object.entries(t.card!.content)){
   if(!plan||cardProblem(t.card,t.type))throw Error('Invalid card plan.');
   for(const [field,type] of [['name','heading'],['price','text'],['image','image']] as const)if(!t.children?.some(n=>n.id===plan.targets[field]&&n.type===type))throw Error('Map direct heading, text and image children.');
   const lang=language as 'en'|'ar';totals[lang]+=(plan.limit-1)*nodes(t).length;counts[lang]+=plan.limit;
  }
 }
 if(Math.max(...Object.values(totals))>500||Math.max(...Object.values(counts))>12)throw Error('Expanded sections exceed 12 cards or page node limit.');
}
export function changeCard(tree:PageNode,nodeId:string,language:'en'|'ar',plan:CardPlan|null):PageNode{
 const next=structuredClone(tree),n=nodes(next).find(n=>n.id===nodeId);if(!n||n.type!=='column')throw Error('Select a native product column.');
 const content={...n.card?.content};if(plan)content[language]=structuredClone(plan);else delete content[language];if(Object.keys(content).length)n.card={schema:cardSchema,content};else delete n.card;assertCardScope(next);return next;
}
const same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b);
export function validCardMedia(src:unknown):src is string{
 if(typeof src!=='string'||/[\x00-\x20\x7f\\%?#]/.test(src)||src.includes('..'))return false;
 const path=/^\/uploads\/t\/[a-f0-9-]{36}\/product_image\/[A-Za-z0-9._/-]+\.(png|jpe?g|gif|webp)$/i;
 if(path.test(src))return true;
 try{const u=new URL(src);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&u.hostname.endsWith('.public.blob.vercel-storage.com')&&/^\/t\/[a-f0-9-]{36}\/product_image\/[A-Za-z0-9._/-]+\.(png|jpe?g|gif|webp)$/i.test(u.pathname)}catch{return false}
}
/** Exact native render-copy verification, with bounded mapped fields only. */
export function validResolvedCards(source:PageNode,resolved:PageNode,lang:'en'|'ar',scalars:(a:PageNode,b:PageNode,l:'en'|'ar')=>boolean):boolean{
 try{
  assertCardScope(source);const next=structuredClone(source),all=nodes(next),templates=all.filter(n=>n.card);if(!templates.length)return scalars(source,resolved,lang);
  for(const t of templates){
  const plan=t.card!.content[lang];if(!plan)return false;
  const parent=all.find(n=>n.children?.some(c=>c.id===t.id))!,out=nodes(resolved).find(n=>n.id===parent.id);
  if(!out){const root=all.find(n=>n.children?.some(c=>c.id===parent.id));if(!root)return false;root.children=root.children!.filter(n=>n.id!==parent.id);continue}
  const cards=out.children??[];if(cards.length<1||cards.length>plan.limit)return false;
  for(const generated of cards){
   const clone=structuredClone(t);delete clone.card;
   const templateNodes=nodes(clone),generatedNodes=nodes(generated);let index=0;
   const visit=(n:PageNode):boolean=>{
    const g=generatedNodes[index++];if(!g||!/^n_[a-f0-9]{16}$/.test(g.id)||g.type!==n.type)return false;
    const old=n.id;n.id=g.id;n.content[lang]={...n.content[lang]};
    if(old===plan.targets.name){const value=g.content[lang]?.text;if(typeof value!=='string'||!value.trim()||value.length>200)return false;n.content[lang]={...n.content[lang],text:value}}
    if(old===plan.targets.price){const value=g.content[lang]?.html;if(typeof value!=='string'||!/^<p>(0|[1-9]\d{0,9})\.\d{2} (EGP|USD|EUR|GBP|SAR|AED)<\/p>$/.test(value))return false;n.content[lang]={...n.content[lang],html:value}}
    if(old===plan.targets.image){const value=g.content[lang];if(!value||!validCardMedia(value.src)||typeof value.alt!=='string'||value.alt.length>200)return false;n.content[lang]={...n.content[lang],src:value.src,alt:value.alt}}
    if(n.children){const kept:PageNode[]=[];for(const child of n.children){const optional=child.id===plan.targets.price||child.id===plan.targets.image;if(optional&&generatedNodes[index]?.type!==child.type)continue;if(!visit(child))return false;kept.push(child)}n.children=kept;}
    return true;
   };
   if(!templateNodes.length||!visit(clone)||index!==generatedNodes.length||!same(clone,generated))return false;
  }
  parent.children=structuredClone(cards);const designed=parent.settings?.desktop?.columns;const count=typeof designed==='number'&&Number.isInteger(designed)&&designed>=1&&designed<=6?Math.min(cards.length,designed):cards.length;parent.settings={...parent.settings,desktop:{...parent.settings.desktop,columns:count}};
  }
  return scalars(next,resolved,lang);
 }catch{return false}
}
