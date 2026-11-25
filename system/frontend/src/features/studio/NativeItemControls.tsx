import {useEffect,useState} from 'react';
import type {PageNode} from './pagetree';
import {itemBindingSchema,itemBindingTargets,type NativeItemBinding} from './nativeBindings';
import {getUILang,t} from './uiStrings';
import {siteRequestHeaders} from './sitePages';

type Consent={products:string[];show_price:boolean;show_image:boolean;schema?:string};
type Choice={id:string;name:string};
const V2='mizan.inventory-website-cards.experimental.v2';

/** Individually bound elements: bind this element to one consented product record. */
export default function NativeItemControls({node,language,apiBase,onChange}:{node:PageNode;language:'en'|'ar';apiBase:string;onChange:(binding:NativeItemBinding|null)=>void}){
 const ar=true;
 const target=itemBindingTargets[node.type];
 const field=target?Object.keys(target)[0]:'';
 const binding=(node.bindings?.schema===itemBindingSchema?node.bindings.content[language]?.[field]:undefined) as NativeItemBinding|undefined;
 const [products,setProducts]=useState<Choice[]>([]),[consent,setConsent]=useState<Consent|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false),[open,setOpen]=useState(false);
 useEffect(()=>{setOpen(!!binding);setError('');if(binding)void load()},[node.id,language]);
 async function request(path:string){const r=await fetch(apiBase+path,{credentials:'include',headers:siteRequestHeaders(apiBase,'GET',false,document.cookie)});if(!r.ok)throw Error(`Product display consent unavailable (${r.status}).`);return r.json()}
 async function load(){setOpen(true);setLoading(true);setError('');try{
  const [p,c]=await Promise.all([request('/site/module-settings/inventory/cards'),request('/site/module-settings/inventory/choices')]);
  const policy=p.value as Consent;
  if(!policy||!Array.isArray(policy.products)||!Array.isArray(c.products?.items))throw Error('Product display consent response unverified.');
  const allowed=new Set(policy.products);
  setConsent(policy);
  setProducts((c.products.items as Choice[]).filter(x=>allowed.has(x.id)&&typeof x.name==='string'));
 }catch(e){setError(e instanceof Error?e.message:(ar?t('تعذّر التأكد من موافقة عرض المنتجات. المحتوى الحالي ما اتغيرش.'):'Product display consent could not be verified. The current content is unchanged.'));}finally{setLoading(false)}}
 const fields=target?target[field]:[];
 const currentName=binding&&products.find(p=>p.id===binding.item_key)?.name;
 return <section className="native-data-controls"><strong>{ar?t('بيانات العنصر'):'Element data'}</strong><div className="data-mode"><button type="button" aria-pressed={!binding} onClick={()=>{onChange(null);setOpen(false)}}>{ar?t('ثابت'):'Static'}</button><button type="button" aria-pressed={!!binding} onClick={load}>{ar?t('منتج'):'Product'}</button></div>{binding&&<p role="status">{ar&&getUILang()==='ar'?`متصل بمنتج${currentName?`: ${currentName}`:''}. الحقل: ${binding.field}. محفوظ مع المسودة دي. معاينة بتسجيل دخول بس.`:`Connected to a product${currentName?`: ${currentName}`:''}. Field: ${binding.field}. Saved with this draft. Authenticated preview only.`}</p>}{open&&<><p>{ar?t('اربط العنصر ده بمنتج واحد من المنتجات الموافق على عرضها. الاسم أو سعر العرض أو الصورة المملوكة بس، حسب الحقل. المنتج الملغي أو غير الموافق عليه بيخفي العنصر.'):'Bind this element to one product from your consented display products. Name, display price or owned image only, depending on the field. A revoked or unconsented product hides the element.'}</p>{consent&&consent.schema!==V2&&<p role="status">{ar?t('موافقتك المحفوظة أقدم من صياغة العناصر المربوطة منفردة. احفظ سياسة عرض المنتجات تاني من بيانات الموديول عشان تشملها.'):'Your saved consent predates the individually bound elements wording. Save the product display policy again from Module data to include them.'}</p>}{loading?<p role="status">{ar?t('بنتأكد من المنتجات الموافق عليها…'):'Checking consented products...'}</p>:products.map(p=><button type="button" className="data-source" key={p.id} aria-pressed={binding?.item_key===p.id} onClick={()=>onChange({mode:'dynamic',module:'inventory',source:'products',item_key:p.id,field:binding&&fields.includes(binding.field)?binding.field:fields[0],on_missing:binding?.on_missing??'hide'})}><span className="data-example" aria-hidden="true">Aa</span><span>{p.name}<small>{ar?t('منتج موافق على عرضه · معاينة مقفولة بحسابك'):'Consented display product · authenticated preview'}</small></span></button>)}{!loading&&!products.length&&!error&&<p>{ar?t('مفيش منتجات موافق على عرضها. احفظ موافقة عرض المنتجات من بيانات الموديول الأول.'):'No consented display products. Save product display consent in Module data first.'}</p>}{error&&<p role="alert">{error}</p>}{binding&&fields.length>1&&<label>{ar?t('الحقل المعروض'):'Displayed field'}<select aria-label="Item binding field" value={binding.field} onChange={e=>onChange({...binding,field:e.target.value as NativeItemBinding['field']})}>{fields.map(f=><option key={f} value={f}>{f==='name'?(ar?t('اسم المنتج'):'Product name'):(ar?t('سعر العرض'):'Display price')}</option>)}</select></label>}{binding&&<label>{ar?t('لو المنتج مش متاح'):'If the product is unavailable'}<select aria-label="Item binding missing behavior" value={binding.on_missing} onChange={e=>onChange({...binding,on_missing:e.target.value as 'hide'|'empty'})}><option value="hide">{ar?t('إخفاء العنصر'):'Hide this element'}</option><option value="empty">{ar?t('إظهار عنصر فاضي'):'Show an empty element'}</option></select></label>}</>}</section>;
}
