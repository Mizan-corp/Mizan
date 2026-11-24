import {nativeProjectionMap} from './nativeProjectionMap';
import NativeCardControls from './NativeCardControls';
import {changeCard,type CardPlan} from './nativeCards';
import WebsiteModuleSettings from './WebsiteModuleSettings';
import NativeRepeatControls from './NativeRepeatControls';
import NativeDataControls from './NativeDataControls';
import {hasBindings,changeBinding,changeRepeat,validResolvedTree,type NativeBinding,type NativeRepeatPlan} from './nativeBindings';
import {updatedPageTitles,pageTitlesKey} from './pageTitles';
import { useEffect, useRef, useState } from 'react';
import { changeStructure, childTypes, newNativeId, type StructureEdit } from './nativeStructure';
import { readableName, readableType } from './nativePresets';
const AR_TYPES:Record<string,string>={page:'صفحة',section:'قسم',columns:'صف أعمدة',column:'عمود',heading:'عنوان',text:'نص',image:'صورة',button:'زر',divider:'فاصل',spacer:'مسافة',gallery:'معرض',cards:'بطاقات',form:'نموذج',video:'فيديو',map:'خريطة',list:'قائمة',quote:'اقتباس'};
const arType=(tp:string)=>AR_TYPES[tp]?t(AR_TYPES[tp]):readableType(tp);
import NativeDragCanvas from './NativeDragCanvas';
import NativeContentControls from './NativeContentControls';
import NativeLibrary from './NativeLibrary';
import NativeChrome from './NativeChrome';
import LibraryOverview from './LibraryOverview';
import { createSitePagesClient, type PageDetail, type PageSummary, type PublicAccess, type Revision, SiteApiError } from './sitePages';
import { assertNativeTree, nativeTreeKey, nativeChange, nativeNodes, nativeUndo, nativeRedo, nativeSettingChoices, type NativeHistory, type NativeEdit, type NativeDevice } from './nativeTree';
import TreePreview, { type ThemeSpec } from './treerender';
import type {PageNode} from './pagetree';
import { createOperationGate } from './saveState';
import {t,getUILang,useUILang,setUILang,uiDir,type UILang} from './uiStrings';

function arPreflight(detail:string):string{
 const urls=detail.match(/https?:\/\/[^\s,]+/g)||[];
 const host=(detail.match(/only allow addresses on ([^\s.]+[^\s.]*)/)||[])[1];
 const list=urls.length?urls.join(t('، ')):t('عناوين خارجية');
 if(detail.startsWith('This page cannot be published for the public test host'))return getUILang()==='en'?`This page has external addresses (${list}) and cannot be published on the public test host. Public pages on the trial domain only allow addresses on ${host?host+' ':''}or relative links. Replace or remove them and publish again. The previously published version is unchanged.`:`الصفحة دي فيها عناوين خارجية (${list}) ومينفعش تتنشر على مضيف الاختبار العام. الصفحات العامة في النطاق التجريبي بتسمح بس بعناوين على ${host?host+' ':''}أو روابط نسبية. بدّلها أو شيلها وانشر تاني. النسخة المنشورة السابقة زي ما هي.`;
 if(detail.startsWith('This page cannot be made public'))return getUILang()==='en'?`This page has external addresses (${list}) and cannot be made public right now. Only ${host?host+' ':''}addresses or relative links are allowed. Edit the page, publish it again, then enable public access. The page stays private until then.`:`الصفحة دي فيها عناوين خارجية (${list}) ومينفعش تتاح للعامة دلوقتي. المسموح بس عناوين ${host?host+' ':''}أو روابط نسبية. عدّل الصفحة وانشرها تاني وبعدين فعّل الإتاحة العامة. الصفحة بتفضل خاصة لحد كده.`;
 if(detail.startsWith('This address has a managed connected-data activation'))return getUILang()==='en'?'This address has a managed connected-data activation. Re-enabling public access needs the separately approved operation; the page stays private.':'العنوان ده عليه تفعيل بيانات متصلة مُدار. إعادة تفعيل الإتاحة العامة محتاجة العملية المعتمدة بشكل منفصل؛ الصفحة بتفضل خاصة.';
 if(detail.startsWith('Pages that read business data cannot be made public'))return getUILang()==='en'?'Pages that read business data cannot be made public in synthetic scope. Remove the connected-data elements first; the page stays private.':'الصفحات اللي بتقرا بيانات الشغل مينفعش تتاح للعامة في النطاق التجريبي. شيل العناصر المربوطة بالبيانات الأول؛ الصفحة بتفضل خاصة.';
 if(detail.startsWith('This page is public in synthetic scope'))return getUILang()==='en'?'This page is public in synthetic scope, which cannot serve connected data. Disable public access first, then publish again. The previously published version is unchanged.':'الصفحة دي متاحة للعامة في النطاق التجريبي، وده مبيقدمش بيانات متصلة. وقّف الإتاحة العامة الأول، وبعدين انشر تاني. النسخة المنشورة السابقة زي ما هي.';
 return '';
}
export default function NativeStudio({apiBase='/__studio/api',previewLabel:_previewLabel,onHome}:{apiBase?:string;previewLabel?:string;onHome?:()=>void}={}){
  const uiLang=useUILang();
  const api=useRef(createSitePagesClient({baseUrl:apiBase})).current;
  const [history,setHistory]=useState<NativeHistory|null>(null);
  const [page,setPage]=useState<PageDetail|null>(null);
  const [selected,setSelected]=useState('');
  const [libraryView,setLibraryView]=useState<'overview'|'pages'>('overview');
  const [previewTheme,setPreviewTheme]=useState<ThemeSpec|undefined>();
  const [designIntent,setDesignIntent]=useState<{id:string}>();
  const [assetIntent,setAssetIntent]=useState<{kind:'block'|'template';id:string}>();
  const [sharedDirty,setSharedDirty]=useState(false);
  const [chromeTarget,setChromeTarget]=useState<{part:'header'|'footer'|'design'}>({part:'header'});
  const [motionReplay,setMotionReplay]=useState(0);
  const [moduleDirty,setModuleDirty]=useState(false);
  const [panel,rawSetPanel]=useState<'add'|'layers'|'templates'|'explorer'|'motion'|'chrome'|'connect'|null>(null);
  const setPanel=(next:typeof panel)=>{if(panel==='connect'&&next!=='connect'&&moduleDirty&&!window.confirm('Discard unsaved website module settings? Saved values will stay unchanged.'))return;if(next!=='connect')setModuleDirty(false);rawSetPanel(next)};
  const [recoveryPages,setRecoveryPages]=useState<PageSummary[]>([]),[recoveryError,setRecoveryError]=useState('');
  const [pageId,setPageId]=useState(()=>new URLSearchParams(location.search).get('page')??'');
  const [lang,setLang]=useState<'en'|'ar'>('en');
  const [device,setDevice]=useState<NativeDevice>(()=>window.innerWidth<700?'mobile':'desktop');
  const [previewOnly,setPreviewOnly]=useState(false);
  const [dragging,setDragging]=useState(false);
  useEffect(()=>{const change=(e:Event)=>setDragging(!!(e as CustomEvent).detail);addEventListener('native-drag-state',change);return()=>removeEventListener('native-drag-state',change)},[]);
  const [notice,setNotice]=useState('Loading an explicit backend page. No browser-project fallback.');
  const [saved,setSaved]=useState('');
  const [titles,setTitles]=useState<Record<string,string>>({}),[savedTitles,setSavedTitles]=useState<Record<string,string>>({});
  const [titleOpen,setTitleOpen]=useState(false),[titleValue,setTitleValue]=useState(''),[titleError,setTitleError]=useState('');
  const [titleLanguage,setTitleLanguage]=useState<'en'|'ar'>('en');
  const [busy,setBusy]=useState(false);
  const [theme,setTheme]=useState<ThemeSpec|undefined>();
  
  const [conflict,setConflict]=useState(false);
  const [error,setError]=useState('');
  const gate=useRef(createOperationGate());
  const current=useRef(history);current.current=history;
  const key=history?nativeTreeKey(history.tree):'';
  const [dataRevision,setDataRevision]=useState(0);
  const [tbPos,setTbPos]=useState<{top:number;left:number}|null>(null);
  const [publishOpen,setPublishOpen]=useState(false);
  const [pubBusy,setPubBusy]=useState(false);
  const [pubDone,setPubDone]=useState(false);
  const [pubError,setPubError]=useState('');
  const [pubAccess,setPubAccess]=useState<PublicAccess|null>(null);
  const [revisions,setRevisions]=useState<Revision[]>([]);
  const [resolved,setResolved]=useState<{key:string;tree:PageNode}|null>(null),[dataError,setDataError]=useState('');
  const dynamic=!!history&&hasBindings(history.tree);
  const resolutionKey=key+'|'+lang+'|'+device+'|'+dataRevision;
  useEffect(()=>{
    if(!history||!dynamic){setResolved(null);setDataError('');return;}
    let cancelled=false;setDataError('');
    const timer=setTimeout(()=>{api.previewData(history.tree,lang,device).then(result=>{
      if(cancelled)return;assertNativeTree(result.tree);if(hasBindings(result.tree)||!validResolvedTree(history.tree,result.tree,lang))throw Error('Unverified preview projection.');setResolved({key:resolutionKey,tree:result.tree});
    }).catch(()=>{if(!cancelled){setResolved(null);setDataError('Dynamic preview unavailable. No static fallback is shown. Your draft remains in the editor.')}})},350);
    return()=>{cancelled=true;clearTimeout(timer)};
  },[resolutionKey,dynamic]);
  const bindingChange=(binding:NativeBinding|null)=>{
    if(!history||!node)return;
    try{const tree=changeBinding(history.tree,node.id,lang,binding);assertNativeTree(tree);setHistory({tree,past:[...history.past.slice(-29),history.tree],future:[]});}catch(e){setNotice(e instanceof Error?e.message:'Binding refused.')}
  };
  const repeatChange=(plan:NativeRepeatPlan|null)=>{
    if(!history||!node)return;
    try{const tree=changeRepeat(history.tree,node.id,lang,plan);assertNativeTree(tree);setHistory({tree,past:[...history.past.slice(-29),history.tree],future:[]});}catch(e){setNotice(e instanceof Error?e.message:'Repeat refused.')}
  };
  const cardChange=(plan:CardPlan|null)=>{
    if(!history||!node)return;
    try{const tree=changeCard(history.tree,node.id,lang,plan);assertNativeTree(tree);setHistory({tree,past:[...history.past.slice(-29),history.tree],future:[]});}catch(e){setNotice(e instanceof Error?e.message:'Product card refused.')}
  };
  const titlesDirty=pageTitlesKey(titles)!==pageTitlesKey(savedTitles);
  const titleInputDirty=titleOpen&&titleValue!==(titles[titleLanguage]??'');
  const dirty=key!==saved||titlesDirty||titleInputDirty;
  useEffect(()=>{
    const viewport=window.visualViewport;
    const syncViewport=()=>document.documentElement.style.setProperty('--studio-visible-height',`${viewport?.height??window.innerHeight}px`);
    syncViewport();viewport?.addEventListener('resize',syncViewport);
    return()=>{viewport?.removeEventListener('resize',syncViewport);document.documentElement.style.removeProperty('--studio-visible-height')};
  },[]);
  useEffect(()=>{
    if(window.innerWidth>=700||!selected||selected===history?.tree.id)return;
    requestAnimationFrame(()=>{const canvas=document.querySelector('.studio-canvas'),el=document.getElementById(selected);if(canvas&&el){const a=canvas.getBoundingClientRect(),b=el.getBoundingClientRect();canvas.scrollBy({top:b.top-a.top-120,behavior:'instant'});}});
  },[selected]);
  useEffect(()=>{
    let cancelled=false;
    (async()=>{
      try{
        const id=pageId;if(!id)throw Error('Open an explicit ?editor=tree&page=PAGE_ID link.');
        const detail=await api.getPage(id);if(cancelled)return;
        if(detail.id!==id)throw Error('Backend returned a different page identity.');
        if(!/^[0-9a-f]{64}$/.test(detail.edit_token??''))throw Error('Backend has no native conflict-protection token. Update the backend before editing.');
        if(detail.status==='archived')throw Error('Archived page is read-only.');
        const tree=detail.draft_tree??detail.published_tree;if(!tree)throw Error('This editor needs an existing supported tree.');
        assertNativeTree(tree);
        try {const settings=await api.getSettings();if(cancelled)return;setTheme(structuredClone(settings.value));}
        catch {if(cancelled)return;}
        setPage(detail);setTitles(detail.titles);setSavedTitles(detail.titles);setTitleOpen(false);setHistory({tree:structuredClone(tree),past:[],future:[]});setSaved(nativeTreeKey(tree));setSelected(tree.id);
        setLang(Object.keys(detail.titles).includes('en')?'en':'ar');setNotice('Native tree loaded. IDs, other languages and untouched fields are preserved. Local test backend only.');
      }catch(e){if(!cancelled)setError(e instanceof Error?e.message:'Load failed. Source is protected.');}
    })();return()=>{cancelled=true};
  },[pageId]);
  useEffect(()=>{
    if(!busy&&!moduleDirty&&(!key||!dirty))return;
    const warn=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue=''};
    addEventListener('beforeunload',warn);return()=>removeEventListener('beforeunload',warn);
  },[key,saved,busy,titlesDirty,titleInputDirty,moduleDirty]);
  const edit=(operation:NativeEdit)=>{
    if(!history)return;
    try{setHistory(nativeChange(history,operation));setNotice('Unsaved native tree edit. No project reconstruction.');}catch(e){setNotice(`Edit refused: ${e instanceof Error?e.message:'unsupported operation'}`);}
  };
  const structure=(operation:StructureEdit,confirmed=false)=>{
    if(!history)return;
    if(operation.kind==='template'&&!confirmed&&!window.confirm('Replace this page body with the template? Page identity and shared site appearance stay unchanged. Undo restores the previous body before leaving.'))return;
    try{const next=changeStructure(history,operation);setHistory(next);if(operation.kind==='insert')setSelected(operation.id);else if(operation.kind==='remove')setSelected(next.tree.id);else if(operation.kind==='template'){setLang('en');setSelected(next.tree.id);setPanel(null);}else if(operation.kind==='preset'){setSelected(next.tree.children![operation.index??next.tree.children!.length-1].id);setPanel(null);}setNotice('Unsaved structure edit. Existing node IDs retained. Column-count changes are limited to the edited row.');}
    catch(e){setNotice(`Structure edit refused: ${e instanceof Error?e.message:'unsupported operation'}`)}
  };
  const save=async()=>{
    if(!history||!page||conflict||!gate.current.start())return;
    const snapshot=structuredClone(history.tree),snapshotKey=nativeTreeKey(snapshot),titleSnapshot=structuredClone(titles);setBusy(true);setNotice('Saving native tree snapshot...');
    try{
      const detail=await api.saveTreeDraft(page.id,snapshot,page.edit_token,titleSnapshot);
      if(!/^[0-9a-f]{64}$/.test(detail.edit_token??'')||detail.status==='archived'||detail.id!==page.id||nativeTreeKey(detail.draft_tree)!==snapshotKey||pageTitlesKey(detail.titles)!==pageTitlesKey(titleSnapshot))throw Error('Backend response differs from the submitted tree. Save not verified.');
      setPage(detail);setSaved(snapshotKey);setSavedTitles(titleSnapshot);setNotice(nativeTreeKey(current.current?.tree)===snapshotKey?'Page saved. Your live website has not changed.':'Earlier native snapshot saved. Newer edits remain unsaved.');
    }catch(e){if(e instanceof SiteApiError&&e.isConflict)setConflict(true);setNotice(`Native save failed or unverified: ${e instanceof Error?e.message:'unreachable'}. Editor copy retained.`);}
    finally{gate.current.finish();setBusy(false);}
  };
  const openPublish=async()=>{
    if(!page)return;
    setPublishOpen(true);setPubDone(false);setPubError('');
    try{const [acc,revs]=await Promise.all([api.getPublicAccess(page.id),api.listRevisions(page.id)]);setPubAccess(acc);setRevisions(revs.items)}
    catch{setPubAccess(null);setRevisions([])}
  };
  const doPublish=async()=>{
    if(!page||pubBusy)return;
    setPubBusy(true);setPubError('');
    try{
      const detail=await api.publish(page.id);
      if(detail.id!==page.id||!detail.published)throw Error('Publish response could not be verified.');
      setPage(detail);
      const [acc,revs]=await Promise.all([api.getPublicAccess(page.id),api.listRevisions(page.id)]);setPubAccess(acc);setRevisions(revs.items);setPubDone(true);
    }catch(e){setPubError(e instanceof SiteApiError?(e.isAuth?t('انتهت الجلسة. سجّل دخول من جديد، تغييراتك المحفوظة زي ما هي.'):e.isForbidden?t('الحساب ده مش من حقه ينشر الصفحة دي.'):e.isConflict?(arPreflight(e.detail||'')||t('النشر اترفض: ')+(e.detail||t('تعارض مع الحالة الحالية.'))):e.isInvalid?(arPreflight(e.detail||'')||t('النشر اترفض في مراجعة ما قبل النشر. المسودة محفوظة والنسخة المنشورة زي ما هي.')):e.message):t('تعذّر النشر. حاول تاني.'));}
    finally{setPubBusy(false)}
  };
  const togglePublic=async()=>{
    if(!page||!pubAccess||pubBusy)return;
    setPubBusy(true);setPubError('');
    try{setPubAccess(await api.setPublicAccess(page.id,!pubAccess.enabled))}
    catch(e){setPubError(e instanceof SiteApiError?(e.isForbidden?t('الحساب ده مش من حقه يغيّر الإتاحة.'):e.isConflict?(arPreflight(e.detail||'')||t('الإتاحة العامة اترفضت. الصفحة بتفضل خاصة.')):e.isInvalid?(arPreflight(e.detail||'')||t('مراجعة ما قبل النشر رفضت الإتاحة العامة. الصفحة بتفضل خاصة.')):t('تعذّر تغيير الإتاحة. حاول تاني.')):t('تعذّر تغيير الإتاحة. حاول تاني.'))}
    finally{setPubBusy(false)}
  };
  const doRollback=async(rid:string)=>{
    if(!page||pubBusy||!window.confirm(t('رجّع النسخة دي للمسودة؟ مسودتك الحالية هتتستبدل بمحتوى النسخة المختارة. النسخة العامة مش بتتغير غير بعد ما تنشر من تاني.')))return;
    setPubBusy(true);setPubError('');
    try{
      const detail=await api.rollback(page.id,rid);
      if(detail.id!==page.id)throw Error('Rollback response could not be verified.');
      setPublishOpen(false);
      setNotice(t('النسخة اترجعت للمسودة. الصفحة بتتحمل من جديد بالمحتوى المسترجع. النسخة العامة زي ما هي لحد ما تنشر.'));
      openPage(detail.id);
    }catch(e){setPubError(e instanceof SiteApiError?(e.isForbidden?t('الحساب ده مش من حقه يرجّع النسخ.'):e.message):t('تعذّر الترجيع. حاول تاني.'))}
    finally{setPubBusy(false)}
  };
  const urlLine=(u:string)=><span dir="ltr" className="mz-url">{u.split('/').map((seg,i)=><span key={i}>{i>0?'/':''}{seg}<wbr/></span>)}</span>;
  const openPage=(id:string)=>{
    if(busy||id===pageId)return;
    if(moduleDirty&&!window.confirm('Discard unsaved website module settings before opening this page?'))return;
    if(sharedDirty){setPanel('chrome');return;}
    if(history&&dirty&&!window.confirm('This page has unsaved changes. Discard them and open the selected page?'))return;
    const url=new URL(location.href);url.searchParams.set('page',id);window.history.replaceState(null,'',url);
    setHistory(null);setPage(null);setSaved('');setSelected('');setConflict(false);setError('');setTheme(undefined);setNotice('Opening selected page...');setPanel(previewOnly?null:'explorer');setPageId(id);
  };
  async function followDraftLink(href:string){
    if(!previewOnly||busy)return;
    try{const result=await api.listPages();const matches=result.items.filter(p=>'/'+p.slug===href&&p.status!=='archived'&&p.has_draft);if(matches.length!==1){setNotice('This destination is not an available private draft. No external link was opened.');return;}openPage(matches[0].id)}catch{setNotice('Private draft navigation unavailable. No external link was opened.')}
  }
  useEffect(()=>{
    const clearSpace=()=>document.querySelectorAll('.mz-tb-below,.mz-tb-above').forEach(n=>n.classList.remove('mz-tb-below','mz-tb-above'));
    if(!selected||selected===history?.tree.id||previewOnly){clearSpace();setTbPos(null);return;}
    const update=()=>{
      const el=document.getElementById(selected);const tb=document.querySelector<HTMLElement>('.context-toolbar');
      if(!el||!tb){clearSpace();setTbPos(null);return;}
      clearSpace();
      const w=tb.offsetWidth||320,h=tb.offsetHeight||48;
      const frame=el.closest('.preview-frame');
      const others=[...(frame?frame.querySelectorAll('.mz-node'):[])].filter(n=>n!==el&&!n.contains(el)&&!el.contains(n)).map(n=>n.getBoundingClientRect()).filter(o=>o.width>0&&o.height>0);
      const free=(t:number,l:number)=>!others.some(o=>!(l+w<=o.left||l>=o.right||t+h<=o.top||t>=o.bottom));
      const clampX=(x:number)=>Math.min(Math.max(x,8),Math.max(8,window.innerWidth-w-8));
      const xs=(r:DOMRect)=>[r.left+r.width/2-w/2,r.left,r.right-w].map(clampX);
      let r=el.getBoundingClientRect();
      let placed=false;
      const order=[r.bottom+12+h<=window.innerHeight-10?'below':'above','below','above'].filter((m,i,a)=>a.indexOf(m)===i);
      for(const m of order){
        const t=m==='below'?r.bottom+12:r.top-h-38;
        if(t<70||t+h>window.innerHeight-10)continue;
        for(const l of xs(r))if(free(t,l)){setTbPos({top:t,left:l});placed=true;break;}
        if(placed)break;
      }
      if(!placed){
        const mode=r.bottom+12+h<=window.innerHeight-10?'below':'above';
        el.classList.add(mode==='below'?'mz-tb-below':'mz-tb-above');
        r=el.getBoundingClientRect();
        setTbPos({top:mode==='below'?r.bottom+10:Math.max(70,r.top-h-38),left:xs(r)[0]});
      }
    };
    const raf=requestAnimationFrame(update);
    const canvas=document.querySelector('.studio-canvas');
    canvas?.addEventListener('scroll',update,{passive:true});
    addEventListener('resize',update);
    return()=>{cancelAnimationFrame(raf);canvas?.removeEventListener('scroll',update);removeEventListener('resize',update);clearSpace()};
  },[selected,device,lang,key,previewOnly,panel]);
  const nodes=history?nativeNodes(history.tree):[];
  const node=nodes.find(n=>n.id===selected);
  useEffect(()=>{if(history&&selected!==history.tree.id)document.getElementById(selected)?.scrollIntoView({block:'nearest',inline:'nearest'})},[selected]);
  return <div dir={uiDir(uiLang)} className={`studio-root native-studio mz-editor ${dragging?'is-dragging':''} ${previewOnly?'preview-only':''} ${panel?'tools-open':''} ${node&&node.id!==history?.tree.id?'selection-open':''}`}>
    <header className="studio-top"><button className="mz-logo-mark mz-home-btn" aria-label={t("رجوع لصفحاتك")} title={t("رجوع لصفحاتك")} onClick={()=>{if(moduleDirty&&!window.confirm('Discard unsaved website module settings?'))return;if(sharedDirty){setPanel('chrome');return;}if(history&&dirty&&!window.confirm('Leave without saving this page? Your last saved version will stay.'))return;onHome?.()}}><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round"><path d="M12 4v13M8 20h8M4 8h16"/><circle cx="7" cy="12.5" r="2.6"/><circle cx="17" cy="12.5" r="2.6"/></svg></button><div className="page-name"><button className="page-title-button" disabled={!page||busy||conflict||page.published} title={page?.published?'Title editing is limited to unpublished drafts. Published title separation is not supported yet.':'Edit the title of this unpublished page'} aria-label="Edit page title" onClick={()=>{setTitleValue(titles[lang]??'');setTitleLanguage(lang);setTitleError('');setTitleOpen(!titleOpen)}}>{titles[lang]??page?.slug??t('بنفتح صفحتك')} <span aria-hidden="true">✎</span></button><span className="crumb">{page?.published?t('منشورة'):t('مسودة')}</span></div><div className="mz-top-center"><div className="mz-seg">{(['desktop','tablet','mobile']as const).map(d=><button key={d} className={device===d?'on':''} aria-pressed={device===d} onClick={()=>setDevice(d)}>{d==='desktop'?t('كمبيوتر'):d==='tablet'?t('تابلت'):t('موبايل')}</button>)}</div></div><div className="top-actions"><label className="ui-lang-switch"><span className="mz-sr">{t('لغة الواجهة')}</span><select aria-label={t('لغة الواجهة')} value={uiLang} onChange={e=>setUILang(e.target.value as UILang)}><option value="en">English</option><option value="ar">العربية</option></select></label><div className="journey-history"><button aria-label={t("تراجع")} title={t("تراجع عن آخر تغيير")} disabled={!history?.past.length} onClick={()=>history&&setHistory(nativeUndo(history))}>↶</button><button aria-label={t("إعادة")} title={t("إعادة التغيير")} disabled={!history?.future.length} onClick={()=>history&&setHistory(nativeRedo(history))}>↷</button></div><span className="mz-saved" role="status"><i/>{error?t('الصفحة غير متاحة'):conflict?t('لم يُحفظ — الصفحة اتغيرت بره'):busy?t('بنحفظ…'):!history?t('بنفتح…'):moduleDirty?t('في تغييرات بيانات لم تُحفظ'):sharedDirty?t('في تغييرات تصميم لم تُحفظ'):!dirty?t('تم حفظ كل التغييرات'):t('في تغييرات لم تُحفظ')}</span><button className="mz-btn ghost" aria-pressed={previewOnly} onClick={()=>setPreviewOnly(!previewOnly)}>{previewOnly?t('رجوع للتعديل'):t('معاينة')}</button><button disabled={!history||busy||conflict||titleOpen} className="mz-btn ghost" title={t("احفظ مسودة الصفحة دي. تصميم الموقع ليه حفظ لوحده.")} onClick={save}>{busy?t('بنحفظ…'):sharedDirty?t('احفظ الصفحة بس'):t('حفظ')}</button><button className="mz-btn primary" disabled={!page||busy||conflict||titleOpen} onClick={()=>void openPublish()}>{t('نشر')}</button></div></header>
    {titleOpen&&<form className="page-title-editor" onSubmit={e=>{e.preventDefault();try{setTitles(updatedPageTitles(titles,titleLanguage,titleValue));setTitleOpen(false)}catch(e){setTitleError(e instanceof Error?e.message:'Check the title.')}}}><label>Page title · {titleLanguage}<input aria-label="Page title for selected language" value={titleValue} maxLength={120} onChange={e=>{setTitleValue(e.target.value);setTitleError('')}} autoFocus disabled={busy||conflict}/></label><p>Changes only this page's title in {titleLanguage}. Address and heading stay unchanged. Use Save changes to keep it. Undo/redo changes canvas content, not this title.</p>{titleError&&<p role="alert">{titleError}</p>}<button type="submit" disabled={busy||conflict}>Use title</button><button type="button" onClick={()=>setTitleOpen(false)}>Cancel</button></form>}
    <div className={`studio-notice ${/failed|refused|Newer|unverified/i.test(notice)?'important-notice':'routine-notice'}`} role="status">{notice}</div>
    {conflict&&<div className="native-conflict" role="alert"><strong>Server page changed. Your edits stay here.</strong><p>Saving is paused to avoid overwriting another session. Export your local page (title and tree) before leaving, then reload deliberately to load the server version.</p><button onClick={()=>{if(!history)return;const url=URL.createObjectURL(new Blob([JSON.stringify({tree:history.tree,titles},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='mizan-unsaved-page.json';a.click();URL.revokeObjectURL(url)}}>Export my unsaved page</button></div>}
    {error&&<div className="studio-protection" role="alert"><strong>Source protected. Native editing unavailable.</strong>{error} Nothing was saved. The existing prototype safeguards remain unchanged.</div>}<div className="studio-workspace"><nav className="studio-rail" aria-label={t("أدوات التحرير")}><button className={panel==='add'?'active':''} onClick={()=>setPanel(panel==='add'?null:'add')}><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg><span>{t('إدراج')}</span></button><button className={panel==='explorer'?'active':''} onClick={()=>setPanel(panel==='explorer'?null:'explorer')}><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><rect x="4" y="3" width="16" height="18" rx="2.5"/><path d="M8 7h8M8 11h8"/></svg><span>{t('الصفحات')}</span></button><button className={panel==='chrome'?'active':''} onClick={()=>{setChromeTarget({part:'design'});setPanel(panel==='chrome'?null:'chrome')}}><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><path d="M12 3a9 9 0 1 0 0 18c1.4 0 2-.9 2-2 0-1.5-1.4-2-1.4-3.4 0-1.2 1-2.1 2.4-2.1h2.4A3.6 3.6 0 0 0 21 10a9 9 0 0 0-9-7Z"/><circle cx="7.5" cy="10.5" r="1.1" fill="currentColor"/><circle cx="10.5" cy="7.5" r="1.1" fill="currentColor"/><circle cx="15" cy="7" r="1.1" fill="currentColor"/></svg><span>{t('النمط')}</span></button><div className="journey-rail-divider"/><button className={panel==='templates'?'active':''} onClick={()=>{setLibraryView('overview');setPanel(panel==='templates'?null:'templates')}}><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="8" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/><rect x="13" y="13" width="8" height="8" rx="2"/></svg><span>{t('المكتبة')}</span></button><button className={panel==='layers'?'active':''} onClick={()=>setPanel(panel==='layers'?null:'layers')}><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/></svg><span>{t('الطبقات')}</span></button>{node&&node.id!==history?.tree.id&&<button className={panel==='motion'?'active':''} onClick={()=>setPanel(panel==='motion'?null:'motion')}><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><path d="M12 4v4M12 16v4M4 12h4M16 12h4M6.3 6.3l2.8 2.8M14.9 14.9l2.8 2.8M6.3 17.7l2.8-2.8M14.9 9.1l2.8-2.8"/></svg><span>{t('الحركة')}</span></button>}<button className={panel==='connect'?'active':''} onClick={()=>setPanel(panel==='connect'?null:'connect')}><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><ellipse cx="12" cy="5.5" rx="8" ry="3"/><path d="M4 5.5V12c0 1.7 3.6 3 8 3s8-1.3 8-3V5.5"/><path d="M4 12v6.5c0 1.7 3.6 3 8 3s8-1.3 8-3V12"/></svg><span>{t('البيانات')}</span></button></nav>
      <aside className="studio-layers" hidden={!panel}><div className="simple-panel-head"><strong>{panel==='add'?t('ضيف على صفحتك'):panel==='templates'?t('أصول الموقع'):panel==='connect'?t('ربط بيانات الموقع'):panel==='explorer'?t('صفحات الموقع'):panel==='motion'?t('تحريك العنصر'):panel==='chrome'?t('تصميم الموقع'):t('طبقات الصفحة')}</strong><button aria-label={t("قفل الأدوات")} onClick={()=>setPanel(null)}>×</button></div>{panel==='connect'&&<WebsiteModuleSettings apiBase={apiBase} onDirty={setModuleDirty} onSaved={()=>setDataRevision(v=>v+1)}/>}<NativeChrome apiBase={apiBase} requestedIdentity={designIntent} onPreview={setPreviewTheme} requestedPart={chromeTarget} active={panel==='chrome'} onDirty={setSharedDirty} onSaved={value=>setTheme(value)}/><h2>{page?.titles[lang]??t('بنحمل الصفحة')}</h2>{!history&&panel==='explorer'&&<div><p>{t('الصفحة دي مش قابلة للتحرير. افتح صفحة مدعومة من تحت.')}</p><button onClick={async()=>{try{const result=await api.listPages();setRecoveryPages(result.items);setRecoveryError('')}catch{setRecoveryError(t('تعذّر تحميل الصفحات. حاول تاني.'))}}}>{t('حمّل صفحات مساحة العمل')}</button>{recoveryError&&<p role="alert">{recoveryError}</p>}{recoveryPages.map(p=><button className="recovery-page" key={p.id} disabled={p.status==='archived'} onClick={()=>openPage(p.id)}>{p.titles[lang]??p.slug} · {p.status}</button>)}</div>}{history&&<><div className="native-panel-tabs"><button aria-pressed={panel==='add'} onClick={()=>setPanel('add')}>{t('إضافة')}</button><button aria-pressed={panel==='layers'} onClick={()=>setPanel('layers')}>{t('الطبقات')}</button></div><div hidden={panel!=='add'}><NativeLibrary requestedPreview={assetIntent?.kind==='block'?assetIntent:undefined} mode="blocks" tree={history.tree} theme={theme} lang={lang} pageId={pageId} busy={busy} loadPages={api.listPages} onOpen={openPage} onBlock={preset=>structure({kind:'preset',preset})} onTemplate={template=>{if(!window.confirm(t('تستبدل جسم الصفحة بالقالب؟ هوية الصفحة وتصميم الموقع المشترك بيفضلوا زي ما هما. التراجع بيرجّع الجسم السابق قبل المغادرة.')))return false;structure({kind:'template',template},true);return true;}}/><details className="library-basic"><summary>{t('عناصر فردية')}</summary><div className="native-add-tools"><h3>{t('إضافة عناصر')}</h3><p className="hint">{t('اسحب للصفحة، أو اختار مكان بالكيبورد.')}</p><div id="native-add-panel"/></div></details></div>{panel==='motion'&&node&&<div className="motion-controls"><div key={motionReplay+String(node.settings[device]?.animation)} className={`motion-demo mz-animation-${node.settings[device]?.animation??node.settings.desktop?.animation??'none'} mz-animation-speed-${node.settings[device]?.animation_speed??node.settings.desktop?.animation_speed??'normal'} mz-animation-delay-${node.settings[device]?.animation_delay??node.settings.desktop?.animation_delay??'none'}`}>{arType(node.type)}</div><p className="motion-note">{t('اختار تأثير دخول للعنصر ده على')} {device==='desktop'?t('الكمبيوتر'):device==='tablet'?t('التابلت'):t('الموبايل')}{t('. لوحة التحرير بتفضل ثابتة. المعاينة تحت، والحركة بتتحفظ مع الصفحة.')}</p><div className="motion-options">{['none','fade','rise','slide','zoom'].map(effect=><button key={effect} aria-pressed={(node.settings[device]?.animation??node.settings.desktop?.animation??'none')===effect} onClick={()=>{edit({kind:'setting',id:node.id,device,field:'animation',value:effect});setMotionReplay(n=>n+1)}}>{effect==='none'?t('بدون حركة'):effect==='rise'?t('صعود هادي'):effect==='slide'?t('انزلاق'):effect==='zoom'?t('تقريب ناعم'):t('ظهور تدريجي')}</button>)}</div>{(['animation_speed','animation_delay'] as const).map(field=><label key={field}>{field==='animation_speed'?t('السرعة'):t('التأخير')}<select aria-label={field==='animation_speed'?'Animation speed':'Animation delay'} value={String(node.settings[device]?.[field]??node.settings.desktop?.[field]??(field==='animation_speed'?'normal':'none'))} onChange={e=>edit({kind:'setting',id:node.id,device,field,value:e.target.value})}>{(field==='animation_speed'?['quick','normal','slow']:['none','short','long']).map(v=><option key={v}>{v}</option>)}</select></label>)}<button onClick={()=>setMotionReplay(n=>n+1)}>{t('إعادة الحركة')}</button><p className="motion-note">{t('دخول واحد لكل تحميل صفحة. مفيش تكرار لا نهائي ولا محفزات تمرير. إعدادات الجهاز بترث الكمبيوتر لحد ما تتغير. تفضيلات تقليل الحركة بتطفي كل التأثيرات وبتسيب المحتوى ظاهر.')}</p></div>}{<div hidden={panel!=='templates'||libraryView!=='overview'}><LibraryOverview tree={history.tree} theme={theme} onPage={id=>{setAssetIntent({kind:'template',id});setLibraryView('pages')}} onBlock={id=>{setAssetIntent({kind:'block',id});setPanel('add')}} onMotion={()=>{if(node&&node.id!==history.tree.id)setPanel('motion');else setNotice(t('اختار عنصر على الصفحة، وبعدين افتح تحريك عشان تطبّق الحركة.'))}} onDesign={id=>{if(id)setDesignIntent({id});setChromeTarget({part:'design'});setPanel('chrome')}}/></div>}
{panel==='templates'&&libraryView==='pages'&&<button onClick={()=>setLibraryView('overview')}>Back to all library assets</button>}
{(panel==='explorer'||(panel==='templates'&&libraryView==='pages'))&&<NativeLibrary requestedPreview={panel==='templates'&&assetIntent?.kind==='template'?assetIntent:undefined} mode={panel==='explorer'?'explorer':'templates'} tree={history.tree} theme={theme} lang={lang} pageId={pageId} busy={busy} loadPages={api.listPages} onOpen={openPage} onBlock={preset=>structure({kind:'preset',preset})} onTemplate={template=>{if(!window.confirm('Replace this page body with the template? Page identity and shared site appearance stay unchanged. Undo restores the previous body before leaving.'))return false;structure({kind:'template',template},true);return true;}}/>}<div hidden={panel!=='layers'} className="native-outline"><div className="panel-title">LAYERS</div>{(()=>{const render=(n:typeof history.tree,depth:number):React.ReactNode=><div className="native-layer-group" key={n.id}>{n.children?.length?<details open><summary><button data-node-id={n.id} data-node-type={n.type} className={`native-node ${selected===n.id?'active':''}`} style={{paddingInlineStart:8}} onClick={e=>{e.preventDefault();setSelected(n.id);setPanel(null)}}><b>{readableName(n,lang)}</b><small>{readableType(n.type)}</small></button></summary>{n.children.map(c=>render(c,depth+1))}</details>:<button data-node-id={n.id} data-node-type={n.type} className={`native-node ${selected===n.id?'active':''}`} style={{paddingInlineStart:8}} onClick={()=>{setSelected(n.id);setPanel(null)}}><b>{readableName(n,lang)}</b><small>{readableType(n.type)}</small></button>}</div>;return render(history.tree,0)})()}</div></>}</aside>
      <main className="studio-canvas" onClickCapture={e=>{if(!previewOnly)return;const a=(e.target as HTMLElement).closest('a');if(a){e.preventDefault();e.stopPropagation();void followDraftLink(a.getAttribute('href')??'')}}} onClick={e=>{if(previewOnly)return;const chrome=(e.target as HTMLElement).closest('.mz-site-header,.mz-site-footer');if(chrome){setChromeTarget({part:chrome.classList.contains('mz-site-footer')?'footer':'header'});setPanel('chrome')}}}><div className="canvas-bar">{previewOnly&&<button className="private-preview-exit" onClick={()=>setPreviewOnly(false)}>{t('رجوع للتعديل')}</button>}{previewTheme&&<span className="scope-chip" role="status">{t('معاينة تصميم مؤقتة · لم تُحفظ')}</span>}<span className="canvas-page-name">{previewOnly?t('معاينة مسودة خاصة · الروابط بتفتح المسودات المحفوظة'):''}</span><label><span className="canvas-language-label">{t('اللغة')}</span> <select aria-label={t("لغة المحتوى")} value={lang} onChange={e=>setLang(e.target.value as 'en'|'ar')}><option value="ar">{t('العربية')}</option><option value="en">English</option></select></label></div>{node&&history&&node.id!==history.tree.id&&<div className="context-toolbar" role="toolbar" aria-label={t("أدوات العنصر المحدد")} style={{position:'fixed',top:tbPos?.top??-200,left:tbPos?.left??0,visibility:tbPos?'visible':'hidden'}}><strong>{arType(node.type)}</strong><button className="native-move-handle" aria-label={`${t('تحريك')} ${arType(node.type)}`} style={{touchAction:'none'}} onPointerDown={e=>{e.preventDefault();window.dispatchEvent(new CustomEvent('native-library-drag',{detail:{item:{kind:'node',id:node.id,type:node.type},x:e.clientX,y:e.clientY}}))}}>{t('⠿ تحريك')}</button><button onClick={()=>setPanel(null)}>{t('تعديل المحتوى')}</button><button onClick={()=>{setPanel(null);requestAnimationFrame(()=>{const el=document.querySelector<HTMLDetailsElement>('.layout-details');if(el){el.open=true;el.scrollIntoView({block:'nearest'})}})}}>{t('التنسيق')}</button><span className="context-divider"/><button onClick={()=>structure({kind:'move',id:node.id,direction:-1})}>{t('قدّام')}</button><button onClick={()=>structure({kind:'move',id:node.id,direction:1})}>{t('ورا')}</button><button aria-label={t("إلغاء تحديد العنصر")} onClick={()=>setSelected(history.tree.id)}>×</button></div>}{dynamic&&resolved?.key!==resolutionKey&&<p className="dynamic-preview-status" role="status">{dataError||'Resolving dynamic preview...'}</p>}{history&&<div className={`preview-frame ${device}`} onPointerDownCapture={e=>{if(previewOnly)e.stopPropagation()}}>{previewOnly?<TreePreview tree={dynamic?(resolved?.key===resolutionKey?resolved.tree:({...history.tree,children:[]})):history.tree} lang={lang} device={device} theme={previewTheme??theme}/>:<NativeDragCanvas lang={lang} tree={history.tree} projectionMap={dynamic&&resolved?.key===resolutionKey?nativeProjectionMap(history.tree,resolved.tree,lang):undefined} selected={selected} onSelect={id=>{setSelected(id);setPanel(null)}} onChange={structure}><TreePreview tree={dynamic?(resolved?.key===resolutionKey?resolved.tree:({...history.tree,children:[]})):history.tree} lang={lang} device={device} theme={previewTheme??theme}/></NativeDragCanvas>}</div>}{!previewOnly&&<div className="mz-stagehint">{t('اضغط على أي حاجة عشان تعدّلها')}</div>}</main>
      <aside className="studio-inspector" hidden={!!panel||!node||node.id===history?.tree.id}><div className="simple-panel-head"><strong>{node?arType(node.type):t('تحرير')}</strong><button aria-label={t("قفل إعدادات العنصر")} onClick={()=>history&&setSelected(history.tree.id)}>×</button></div>{node&&<><p className="scope-hint">{t('خليه على ذوقك. التغييرات بتأثر على الصفحة دي بس.')}</p><details className="native-advanced"><summary>{t('تفاصيل متقدمة للعنصر')}</summary><code className="native-id">{node.id}</code><p>{t('هوية ثابتة في المصدر. مب تتغيرش بالتحرير.')}</p></details>{node.type==='column'&&<NativeCardControls key={node.id+lang} node={node} language={lang} apiBase={apiBase} onChange={cardChange}/>} {node.type==='heading'&&<>{!node.repeat&&<NativeDataControls node={node} language={lang} discover={api.discoverData} onChange={bindingChange}/>}<NativeRepeatControls key={node.id+lang} node={node} language={lang} discover={api.discoverData} onChange={repeatChange}/></>}<fieldset disabled={!!node.bindings?.content[lang]?.text||!!node.repeat?.content[lang]} style={{border:0,padding:0,margin:0}}><NativeContentControls node={node} lang={lang} onEdit={(field,value)=>edit({kind:'content',id:node.id,lang,field,value})}/></fieldset><details className="simple-more"><summary>{t('ترتيب أو حذف')}</summary><fieldset className="link-group"><legend>{t('الهيكل')}</legend>{childTypes(node.type).map(type=><button className="add-link" key={type} onClick={()=>{if(history)structure({kind:'insert',parentId:node.id,type,id:newNativeId(history.tree)})}}>+ {t('إضافة')} {arType(type)}</button>)}{history&&node.id!==history.tree.id&&<><div className="link-order"><button onClick={()=>structure({kind:'move',id:node.id,direction:-1})}>{t('قدّم')}</button><button onClick={()=>structure({kind:'move',id:node.id,direction:1})}>{t('أخّر')}</button></div><button className="native-remove" onClick={()=>{if(window.confirm(t('تحذف العنصر ده وكل اللي جواه من المسودة؟ التراجع متاح قبل ما تسيب الصفحة.')))structure({kind:'remove',id:node.id})}}>{t('حذف العنصر')}</button></>}</fieldset></details><details className="simple-more layout-details"><summary>{t('التنسيق وإعدادات الجهاز')}</summary><div className="inspector-divider"/><div className="panel-title">{device==='desktop'?t('إعدادات الكمبيوتر'):device==='tablet'?t('إعدادات التابلت'):t('إعدادات الموبايل')}</div>{Object.entries(nativeSettingChoices(node.type)).map(([field,choices])=>{const explicit=node.settings[device]?.[field];return <label key={field}>{field}<select aria-label={`Native setting ${field}`} value={explicit===undefined?'__inherit':String(explicit)} onChange={e=>{const value=choices.find(v=>String(v)===e.target.value);if(value!==undefined)edit({kind:'setting',id:node.id,device,field,value})}}><option value="__inherit" disabled>{device==='desktop'?t('مش محدد (افتراضي العارض)'):t('موروث من الكمبيوتر')}</option>{choices.map(v=><option key={String(v)} value={String(v)}>{String(v)}</option>)}</select></label>})}<p className="hint">{t('النص بيستخدم شريط تنسيق صغير. الصور والروابط بتستخدم حقول عناوين؛ رفع الميديا مش متوصل. الأنواع غير المدعومة بتمنع التحميل ومش بتختفي بهدوء. ده مش دعم كامل لتنسيق الصفحات.')}</p></details></>}</aside>{publishOpen&&page&&<div className="mz-publish-overlay" onClick={e=>{if(e.target===e.currentTarget&&!pubBusy)setPublishOpen(false)}}><div className="mz-publish-card" role="dialog" aria-modal="true" aria-label={t("نشر الصفحة")}>
      <div className="simple-panel-head"><strong>{pubDone?t('اتنشرت ✓'):t('جاهز تنشر صفحتك؟')}</strong><button aria-label={t("قفل النشر")} disabled={pubBusy} onClick={()=>setPublishOpen(false)}>×</button></div>
      {!pubDone&&<>
      <div className="mz-publish-address"><span>{t('عنوان الصفحة')}</span><b>{urlLine(pubAccess?.url??(`/${page.slug}`))}</b><small>{pubAccess?.enabled?t('العنوان متاح للناس دلوقتي.'):t('العنوان مش متاح للناس لسه. النشر بيحفظ نسخة عامة، والإتاحة ليها زرار لوحدها بعد النشر.')}</small></div>
      <ul className="mz-publish-checks">
      <li className={!dirty&&!moduleDirty&&!sharedDirty?'ok':'warn'}>{!dirty&&!moduleDirty&&!sharedDirty?t('كل التغييرات محفوظة'):<>{t('في تغييرات لسه مش محفوظة. النشر بياخد آخر نسخة محفوظة بس.')} <button className="mz-inline" disabled={busy} onClick={()=>void save()}>{t('احفظ دلوقتي')}</button></>}</li>
      <li className={Object.values(titles).some(x=>typeof x==='string'&&x.trim())?'ok':'warn'}>{Object.values(titles).some(x=>typeof x==='string'&&x.trim())?t('الصفحة ليها عنوان'):t('الصفحة محتاجة عنوان قبل النشر')}</li>
      <li className="info">{page.published?t('الصفحة منشورة قبل كده. النشر بيحدّث النسخة العامة وبيحفظ نسخة جديدة.'):t('أول نشرة للصفحة دي. كل نشر بيتحفظ كنسخة تقدر ترجع لها.')}</li>
      </ul>
      {pubError&&<p role="alert" className="mz-publish-error">{pubError}</p>}
      <div className="mz-publish-actions"><button className="mz-btn primary" disabled={pubBusy||dirty||moduleDirty||sharedDirty||!Object.values(titles).some(x=>typeof x==='string'&&x.trim())} onClick={()=>void doPublish()}>{pubBusy?t('بننشر…'):t('انشر الصفحة')}</button><button className="mz-btn ghost" disabled={pubBusy} onClick={()=>setPublishOpen(false)}>{t('كمان مراجعة')}</button></div>
      </>}
      {pubDone&&<>
      {pubAccess?.url?<div className="mz-publish-linkrow"><a className="mz-publish-link" href={pubAccess.url} target="_blank" rel="noreferrer">{urlLine(pubAccess.url)}</a><button className="mz-inline" onClick={()=>{const u=pubAccess.url??'';if(navigator.clipboard)void navigator.clipboard.writeText(u).then(()=>setPubError(''),()=>setPubError(t('تعذّر نسخ العنوان.')))}}>{t('نسخ العنوان')}</button></div>:<p>{t('الصفحة اتنشرت كنسخة عامة محفوظة.')}</p>}
      <p className="motion-note">{pubAccess?.enabled?t('الصفحة متاحة للناس على العنوان ده.'):t('الصفحة لسه خاصة. فعّل الإتاحة عشان العنوان يفتح للناس.')}</p>
      {pubAccess&&<button className="mz-btn ghost" disabled={pubBusy} onClick={()=>void togglePublic()}>{pubAccess.enabled?t('وقّف الإتاحة'):t('خلّيها متاحة للناس')}</button>}
      {pubError&&<p role="alert" className="mz-publish-error">{pubError}</p>}
      <details className="mz-publish-revisions"><summary>{t('النسخ المحفوظة')} ({revisions.length})</summary>{revisions.map(r=><div className="mz-revision" key={r.id}><span>{t('نسخة')} {r.number}{r.created_at?` · ${new Date(r.created_at).toLocaleString('ar-EG')}`:''}</span><button className="mz-inline" disabled={pubBusy} onClick={()=>void doRollback(r.id)}>{t('رجّع النسخة دي')}</button></div>)}</details>
      <div className="mz-publish-actions"><button className="mz-btn primary" onClick={()=>setPublishOpen(false)}>{t('رجوع للتعديل')}</button></div>
      </>}
      </div></div>}
    </div>
  </div>;
                                                                                                                                                                                                                                                                                                                                                                                                                                                 }
