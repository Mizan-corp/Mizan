import {useState} from 'react';
import type {PageNode} from './pagetree';
import {repeatCardSchema,repeatCategorySchema,type NativeCardSlots,type NativeCardRepeatPlan,type NativeCategoryRepeatPlan} from './nativeBindings';
import {getUILang,t} from './uiStrings';
type Collection={module:string;source:string;max_items:number;fields:Record<string,{type:string;semantic:string}>};
type Offer={module:string;source:string;max:number;slots:NativeCardSlots};
/** Typed slots follow the template column's children: heading needs a plain-text field, text takes money or plain text, image needs media. */
function offerFor(children:PageNode[],c:Collection):Offer|null{
 const kinds=children.map(n=>n.type);
 if(!kinds.length||!kinds.includes('heading')||kinds.some(k=>!['heading','text','image'].includes(k)))return null;
 const entries=Object.entries(c.fields??{});
 const texts=entries.filter(([,s])=>s.type==='text'&&s.semantic==='plain_text').map(([f])=>f);
 const money=entries.filter(([,s])=>s.type==='money').map(([f])=>f);
 const media=entries.filter(([,s])=>s.type==='media').map(([f])=>f);
 if(!texts.length)return null;
 const slots:NativeCardSlots={heading:texts[0]};
 if(kinds.includes('text')){const field=money[0]??texts.find(f=>f!==slots.heading);if(!field)return null;slots.text=field;}
 if(kinds.includes('image')){if(!media.length)return null;slots.image=media[0];}
 return {module:c.module,source:c.source,max:c.max_items,slots};
}
export default function NativeCardRepeatControls({node,language,discover,onChange}:{node:PageNode;language:'en'|'ar';discover:()=>Promise<{collections?:unknown[]}>;onChange:(slots:NativeCardSlots,plan:NativeCardRepeatPlan|null)=>void}){
 const ar=true; // Arabic-first UI chrome, content lang suffix kept
 const repeat=(node.repeat?.schema===repeatCardSchema||node.repeat?.schema===repeatCategorySchema)?node.repeat:undefined;
 const isCategory=node.repeat?.schema===repeatCategorySchema;
 const plan=repeat?.content[language];
 const otherLang=language==='ar'?'en':'ar';const otherPlan=repeat?.content[otherLang];
 const otherName=otherLang==='ar'?t('العربية'):'English';
 const [offers,setOffers]=useState<Offer[]>([]),[open,setOpen]=useState(!!plan),[error,setError]=useState(''),[categoryOffer,setCategoryOffer]=useState<Offer|null>(null);
 async function load(){setOpen(true);setError('');try{const data=await discover();if(!Array.isArray(data.collections))throw Error();const out:Offer[]=[];let category:Offer|null=null;for(const raw of data.collections){const c=raw as Collection;if(!c||typeof c.module!=='string'||typeof c.source!=='string'||!Number.isInteger(c.max_items)||!c.fields)throw Error();const offer=offerFor(node.children??[],c);if(offer){if(c.source==='category_products')category=offer;else out.push(offer);}}setOffers(out);setCategoryOffer(category)}catch{setError(ar?t('تعذّر التأكد من مصادر المجموعات.'):'Collection sources could not be verified.')}}
 const kinds=(node.children??[]).map(n=>n.type);
 const shape=kinds.length&&kinds.includes('heading')&&kinds.every(k=>['heading','text','image'].includes(k));
 return <section className="native-data-controls"><strong>{ar?t('تكرار بطاقة من بيانات الموديول'):'Repeat card from module data'}</strong><p>{ar?t('قالب العمود ده بيتكرر لسجلات مختارة: الاسم في العنوان، وسعر أو نص، وصورة لو موجودة. سجلات الموقع المختارة بس، ومعاينة بتسجيل الدخول بس. مفيش نشر أو دفع.'):'This column template repeats for selected records: a name heading, price or text, and an image when present. Selected website records only, signed-in preview only. No publishing or checkout.'}</p>{!shape&&<p>{ar?t('العمود ده محتاج عنوان، ومعاه نص أو صورة اختياريين بس عشان يبقى قالب بطاقة.'):'This column needs a heading with only optional text or image children to become a card template.'}</p>}{!plan&&otherPlan&&<p role="status">{otherLang==='ar'?t('المجموعة مربوطة للغة العربية بس. الصفحة لما بتتعرض باللغة دي مش بتعرض البطاقات المكررة: اختار نفس المجموعة هنا عشان تظهر.'):t('المجموعة مربوطة للغة الإنجليزية بس. الصفحة لما بتتعرض باللغة دي مش بتعرض البطاقات المكررة: اختار نفس المجموعة هنا عشان تظهر.')}</p>}<button type="button" disabled={!shape||!!node.bindings||!!node.card} onClick={load}>{ar?t('اختار مجموعة'):'Choose collection'}</button>{plan&&repeat&&<><p role="status">{isCategory?(ar&&getUILang()==='ar'?`بيكرر منتجات التصنيف اللي في رابط الصفحة (روابط /c/<id>). معاينة بتسجيل الدخول بتبان فاضية.`:'Repeating the products of the category in the page link (/c/<id> URLs). The signed-in preview shows empty.'):(ar&&getUILang()==='ar'?`بيكرر: ${plan.module} / ${plan.source}. معاينة بس.`:`Repeating: ${plan.module} / ${plan.source}. Preview-only.`)}</p>{plan&&!otherPlan&&<p role="status">{t('المجموعة دي مربوطة للغة دي بس. الصفحات اللي بتتعرض بلغة تانية مش بتعرض البطاقات المكررة: افتح اللغة التانية واختار نفس المجموعة هناك.')}</p>}<label>{ar?t('أقصى عدد عناصر'):'Maximum items'}<input aria-label="Collection maximum items" type="number" min={1} max={24} value={plan.limit} onChange={e=>{const limit=Number(e.target.value);if(Number.isInteger(limit)&&limit>=1&&limit<=24)onChange(repeat.slots,{...plan,limit})}}/></label><button type="button" onClick={()=>onChange(repeat.slots,null)}>{ar?t('شيل المجموعة وسيب العمود الثابت'):'Remove collection, keep static column'}</button></>}{open&&categoryOffer&&<button className="data-source" type="button" onClick={()=>onChange(categoryOffer.slots,{module:'inventory',source:'category_products',category:'route',limit:Math.min(8,categoryOffer.max),on_missing:'hide'} as NativeCategoryRepeatPlan)}><span className="data-example" aria-hidden="true">Aa<br/>Aa</span><span>{ar?t('منتجات تصنيف من رابط الصفحة'):'Category products from the page link'}<small>{ar?t('صفحة تصنيف · التصنيف من رابط /c/<id>'):'Category page · category from the /c/<id> link'}</small></span></button>}{open&&offers.map(o=><button className="data-source" type="button" key={`${o.module}/${o.source}`} onClick={()=>onChange(o.slots,{module:o.module,source:o.source,limit:Math.min(8,o.max),on_missing:'hide'})}><span className="data-example" aria-hidden="true">Aa<br/>Aa</span><span>{o.module} · {o.source}<small>{ar?t('بطاقة مكررة · سجلات الموقع المختارة بس'):'Repeated card · selected website records only'}</small></span></button>)}{open&&!offers.length&&!error&&<p>{ar?t('مفيش مجموعة متوافقة اتحمّلت.'):'No compatible collection loaded.'}</p>}{error&&<p role="alert">{error}</p>}</section>;
}
