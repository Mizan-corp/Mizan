import {useEffect,useMemo,useState} from 'react';
import NativeStudio from './NativeStudio';
import NewPage from './NewPage';
import DraftPageKit from './DraftPageKit';
import {type PreviewConfig} from './previewConfig';
import {t,getUILang,useUILang,uiDir} from './uiStrings';
type Page={id:string;slug:string;titles:Record<string,string>;status:string;updated_at?:string|null;published?:boolean};
function arNum(n:number){return getUILang()==='en'?String(n):n.toLocaleString('ar-EG')}
function pagesWord(n:number){if(n===1)return t('صفحة');if(n===2)return t('صفحتين');if(n>=3&&n<=10)return t('صفحات');return t('صفحة')}
function ago(iso:string|null|undefined):string{
 if(!iso)return '';
 const then=new Date(iso).getTime();if(!Number.isFinite(then))return '';
 const mins=Math.max(0,Math.round((Date.now()-then)/60000));
 if(mins<1)return t('اتعدلت دلوقتي حالًا');
 if(mins<60){if(mins===1)return t('اتعدلت من دقيقة');if(mins===2)return t('اتعدلت من دقيقتين');if(getUILang()==='en')return `Edited ${mins} minutes ago`;if(mins<=10)return `اتعدلت من ${arNum(mins)} دقايق`;return `اتعدلت من ${arNum(mins)} دقيقة`}
 const hours=Math.round(mins/60);
 if(hours<24){if(hours===1)return t('اتعدلت من ساعة');if(hours===2)return t('اتعدلت من ساعتين');if(getUILang()==='en')return `Edited ${hours} hours ago`;if(hours<=10)return `اتعدلت من ${arNum(hours)} ساعات`;return `اتعدلت من ${arNum(hours)} ساعة`}
 const days=Math.round(hours/24);
 if(days===1)return t('اتعدلت إمبارح');
 if(days===2)return t('اتعدلت من يومين');
 if(getUILang()==='en')return `Edited ${days} days ago`;if(days<=10)return `اتعدلت من ${arNum(days)} أيام`;
 return `اتعدلت من ${arNum(days)} يوم`;
}
function greeting():string{
 let hour=new Date().getHours();
 try{hour=Number(new Intl.DateTimeFormat('en-GB',{hour:'2-digit',hour12:false,timeZone:'Africa/Cairo'}).format(new Date()))}catch{/* local hour */}
 return hour<12?t('صباح الفل'):t('مساء الفل');
}
function pageTitle(p:Page):string{return p.titles?.ar||p.titles?.en||p.slug}
function Thumb({tone}:{tone:'store'|'blog'|'land'}){
 const logoBg=tone==='blog'?'var(--amber)':'var(--teal)';
 const ctaBg=tone==='land'?'var(--amber)':'var(--teal)';
 return <div className="mz-mini"><div className="mz-mnav"><div className="mz-mlogo" style={{background:logoBg}}/><div className="mz-mlinks"><i/><i/><i/></div></div><div className="mz-mhero"><div className="l1"/><div className="l2"/><div className="cta" style={{background:ctaBg}}/><div className="mz-mgrid"><i/><i/><i/></div></div></div>;
}
export default function PreviewSession({config}:{config:PreviewConfig}){
  const uiLang=useUILang();
   const go=uiDir(uiLang)==='rtl'?'←':'→';
 const [state,setState]=useState<'checking'|'signin'|'ready'>('checking');
 const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[workspace,setWorkspace]=useState('studio-test');
 const [error,setError]=useState(''),[busy,setBusy]=useState(false),[pages,setPages]=useState<Page[]>([]);
 const [creating,setCreating]=useState(false),[kitOpen,setKitOpen]=useState(false),[query,setQuery]=useState('');
 const [displayName,setDisplayName]=useState('');
 const [pageId,setPageId]=useState(()=>new URLSearchParams(location.search).get('page')??'');
 async function check(){
  const result=await fetch(config.apiBase+'/site/pages',{credentials:'include',cache:'no-store'});
  if(result.status===401){setState('signin');return;}
  if(!result.ok)throw Error(result.status===403?t('الحساب ده مش من حقه يعدّل الموقع ده. سجّل دخولك بحساب الاستوديو بتاعك.'):t('مقدرناش نفتح مساحة العمل. صفحاتك زي ما هي، جرّب تاني.'));
  const data=await result.json();if(!Array.isArray(data.items))throw Error(t('مقدرناش نحمّل صفحاتك. جرّب تاني.'));
  setPages(data.items.filter((p:Page)=>p.status!=='archived'));setState('ready');
  fetch(config.apiBase+'/auth/me',{credentials:'include',cache:'no-store'}).then(r=>r.ok?r.json():null).then(me=>{const n=(me?.full_name??'').trim();if(n)setDisplayName(n.split(/\s+/)[0])}).catch(()=>{});
 }
 useEffect(()=>{check().catch(e=>{setError(e.message);setState('signin')})},[]);
 async function signIn(e:React.FormEvent){e.preventDefault();if(busy)return;setBusy(true);setError('');
  try{const result=await fetch(config.apiBase+'/auth/login',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,tenant_slug:workspace||null})});setPassword('');
   if(!result.ok)throw Error(result.status===429?t('محاولات كتير أوي. استنى دقيقة وبعدين جرّب تاني.'):t('اتأكد من اسم المستخدم وكلمة السر وبعدين جرّب تاني.'));await check();
  }catch(e){setError(e instanceof Error?e.message:t('تسجيل الدخول فشل.'));}finally{setBusy(false)}
 }
 function open(id:string){const url=new URL(location.href);url.searchParams.set('page',id);history.replaceState(null,'',url);setPageId(id)}
 const filtered=useMemo(()=>{const q=query.trim().toLowerCase();if(!q)return pages;return pages.filter(p=>pageTitle(p).toLowerCase().includes(q)||p.slug.toLowerCase().includes(q))},[pages,query]);
 if(pageId)return <NativeStudio apiBase={config.apiBase} onHome={()=>{setPageId('');history.replaceState(null,'',location.pathname);check().catch(()=>{})}}/>;
 if(state==='checking')return <div dir={uiDir(uiLang)} className="mz-home"><div className="mz-checking">{t('بنجهّز مساحة العمل بتاعتك…')}</div></div>;
 if(state==='signin')return <div dir={uiDir(uiLang)} className="mz-home"><div className="mz-signin"><form className="mz-signin-card" onSubmit={signIn} aria-busy={busy}>
  <div className="mz-logo"><div className="mz-logo-mark"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round"><path d="M12 4v13M8 20h8M4 8h16"/><circle cx="7" cy="12.5" r="2.6"/><circle cx="17" cy="12.5" r="2.6"/></svg></div>{t('ميزان ستوديو')}</div>
  <h1>{t('سجّل دخولك')}</h1>
  <p className="mz-sub">{t('ادخل على مساحة العمل بتاعتك عشان تكمّل شغل على صفحاتك. مفيش أي حاجة هتتنشر من غير ما تختار بنفسك.')}</p>
  {error&&<p className="mz-error" role="alert">{error}</p>}
  <fieldset disabled={busy} style={{border:'none',padding:0,margin:0}}>
   <label className="mz-field"><span>{t('اسم المستخدم')}</span><input value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username" required/></label>
   <label className="mz-field"><span>{t('كلمة السر')}</span><input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" required/></label>
   <label className="mz-field"><span>{t('مساحة العمل')}</span><input value={workspace} onChange={e=>setWorkspace(e.target.value)} autoComplete="off" spellCheck={false} style={{direction:'ltr',textAlign:'left'}}/></label>
   <button className="mz-btn primary big" type="submit" style={{width:'100%',justifyContent:'center',marginTop:6}}>{busy?t('بنسجّل دخولك…'):t('دخول')}</button>
  </fieldset>
 </form></div></div>;
 const name=displayName||username.trim();
 return <div dir={uiDir(uiLang)} className="mz-home">
  <div className="mz-topbar">
   <div className="mz-logo"><div className="mz-logo-mark"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round"><path d="M12 4v13M8 20h8M4 8h16"/><circle cx="7" cy="12.5" r="2.6"/><circle cx="17" cy="12.5" r="2.6"/></svg></div>{t('ميزان ستوديو')}</div>
   <div className="mz-wkchip" title={workspace}>{t('مساحة عمل')} {workspace}</div>
   <div className="mz-spacer"/>
   <div className="mz-search-home"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input value={query} onChange={e=>setQuery(e.target.value)} placeholder={t("دوّر على صفحة…")} aria-label={t("دوّر على صفحة")}/></div>
   <div className="mz-avatar" aria-hidden>{name?name[0]:t('م')}</div>
  </div>
  <div className="mz-scroll">
   <div className="mz-hero">
    <div className="mz-overline">{greeting()}{name?(getUILang()==='ar'?` يا ${name}`:` ${name}`):''}</div>
    <h1>{t('إيه اللي هتصنع')} <em>{t('النهارده؟')}</em></h1>
    <p>{t('كمّل على صفحاتك، أو ابدأ من قالب جاهز وعدّله بمزاجك، بالسحب والإفلات ومن غير ما تكتب سطر كود واحد.')}</p>
    <div className="mz-hero-cta">
     <button className="mz-btn primary big" onClick={()=>setCreating(true)}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>{t('صفحة جديدة')}</button>
     <button className="mz-btn ghost big" onClick={()=>document.getElementById('mz-templates')?.scrollIntoView({behavior:'smooth'})}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="2"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2"/></svg>{t('اتفرّج على القوالب')}</button>
    </div>
   </div>
   <div className="mz-sec-head"><h2>{t('صفحاتك')}</h2><span className="mz-count">{arNum(filtered.length)} {pagesWord(filtered.length)}{query.trim()?(getUILang()==='en'?` (of ${pages.length})`:` (من ${arNum(pages.length)})`):''}</span>{query.trim()&&<button className="mz-more" onClick={()=>setQuery('')}>{t('كل الصفحات')} {go}</button>}</div>
   {creating?<NewPage apiBase={config.apiBase} onCancel={()=>setCreating(false)} onCreated={page=>{setCreating(false);open(page.id)}}/>
   :kitOpen?<DraftPageKit apiBase={config.apiBase} onCancel={()=>setKitOpen(false)} onDone={()=>{setKitOpen(false);check().catch(()=>{})}}/>
   :filtered.length===0?<div className="mz-empty">{pages.length===0?t('لسه مفيش صفحات. ابدأ بأول صفحة ليك من الزرار اللي فوق.'):t('مفيش صفحة بالاسم ده.')}</div>
   :<div className="mz-cards">{filtered.map((p,i)=><button key={p.id} className="mz-pcard" onClick={()=>open(p.id)}>
     <div className="mz-thumb"><Thumb tone={(['store','blog','land'] as const)[i%3]}/></div>
     <div className="mz-meta"><div><div className="mz-name">{pageTitle(p)}</div><div className="mz-sub">{ago(p.updated_at)}</div></div><span className={'mz-status '+(p.published||p.status==='published'?'pub':'draft')}>{p.published||p.status==='published'?t('منشورة'):t('مسودة')}</span><span className="mz-go">{go}</span></div>
    </button>)}</div>}
   <div className="mz-sec-head" id="mz-templates"><h2>{t('قوالب تبدأ منها')}</h2><span className="mz-count">{t('صفحات جاهزة تتعدل بمزاجك، وبتتساب كمسودات لحد ما تنشر بنفسك')}</span></div>
   <div className="mz-cards">
    <button className="mz-pcard" onClick={()=>setKitOpen(true)}><div className="mz-thumb" style={{background:'#EFF4F1'}}><Thumb tone="store"/></div><div className="mz-meta"><div><div className="mz-name">{t('مجموعة المتجر التقني')}</div><div className="mz-sub">{t('٤ صفحات مترابطة كمسودات')}</div></div><span className="mz-go">{go}</span></div></button>
    <button className="mz-pcard" onClick={()=>setKitOpen(true)}><div className="mz-thumb" style={{background:'#F7F3EC'}}><Thumb tone="blog"/></div><div className="mz-meta"><div><div className="mz-name">{t('مجموعة صفحات الكتالوج')}</div><div className="mz-sub">{t('٤ صفحات إرشادية كمسودات')}</div></div><span className="mz-go">{go}</span></div></button>
    <button className="mz-pcard" onClick={()=>setCreating(true)}><div className="mz-thumb" style={{background:'#F3EEE7'}}><Thumb tone="land"/></div><div className="mz-meta"><div><div className="mz-name">{t('قالب صفحة من المكتبة')}</div><div className="mz-sub">{t('أنشئ صفحة وطبّق عليها قالب من جوه المحرر')}</div></div><span className="mz-go">{go}</span></div></button>
   </div>
  </div>
 </div>;
}
