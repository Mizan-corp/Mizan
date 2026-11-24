import WebsiteModuleSettings from './WebsiteModuleSettings';
import NativeRepeatControls from './NativeRepeatControls';
import NativeDataControls from './NativeDataControls';
import {hasBindings,changeBinding,changeRepeat,validResolvedTree,type NativeBinding,type NativeRepeatPlan} from './nativeBindings';
import {updatedPageTitles,pageTitlesKey} from './pageTitles';
import { useEffect, useRef, useState } from 'react';
import { changeStructure, childTypes, newNativeId, type StructureEdit } from './nativeStructure';
import { readableName, readableType } from './nativePresets';
import NativeDragCanvas from './NativeDragCanvas';
import NativeContentControls from './NativeContentControls';
import NativeLibrary from './NativeLibrary';
import NativeChrome from './NativeChrome';
import LibraryOverview from './LibraryOverview';
import { createSitePagesClient, type PageDetail, type PageSummary, SiteApiError } from './sitePages';
import { assertNativeTree, nativeTreeKey, nativeChange, nativeNodes, nativeUndo, nativeRedo, nativeSettingChoices, type NativeHistory, type NativeEdit, type NativeDevice } from './nativeTree';
import TreePreview, { type ThemeSpec } from './treerender';
import type {PageNode} from './pagetree';
import { createOperationGate } from './saveState';

export default function NativeStudio({apiBase='/__studio/api',previewLabel:_previewLabel,onHome}:{apiBase?:string;previewLabel?:string;onHome?:()=>void}={}){
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
  const [themeNotice,setThemeNotice]=useState('Loading saved site appearance...');
  const [conflict,setConflict]=useState(false);
  const [error,setError]=useState('');
  const gate=useRef(createOperationGate());
  const current=useRef(history);current.current=history;
  const key=history?nativeTreeKey(history.tree):'';
  const [dataRevision,setDataRevision]=useState(0);
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
        try {const settings=await api.getSettings();if(cancelled)return;setTheme(structuredClone(settings.value));setThemeNotice('Saved site appearance loaded. Page Save never writes shared settings.');}
        catch {if(cancelled)return;setThemeNotice('Saved appearance unavailable. Renderer defaults shown; no settings will be written.');}
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
  const openPage=(id:string)=>{
    if(busy||id===pageId)return;
    if(moduleDirty&&!window.confirm('Discard unsaved website module settings before opening this page?'))return;
    if(sharedDirty){setPanel('chrome');return;}
    if(history&&dirty&&!window.confirm('This page has unsaved changes. Discard them and open the selected page?'))return;
    const url=new URL(location.href);url.searchParams.set('page',id);window.history.replaceState(null,'',url);
    setHistory(null);setPage(null);setSaved('');setSelected('');setConflict(false);setError('');setTheme(undefined);setNotice('Opening selected page...');setPanel('explorer');setPageId(id);
  };
  const nodes=history?nativeNodes(history.tree):[];
  const node=nodes.find(n=>n.id===selected);
  useEffect(()=>{if(history&&selected!==history.tree.id)document.getElementById(selected)?.scrollIntoView({block:'nearest',inline:'nearest'})},[selected]);
  return <div className={`studio-root native-studio simple-studio canva-studio journey-studio ${dragging?'is-dragging':''} ${previewOnly?'preview-only':''} ${panel?'tools-open':''} ${node&&node.id!==history?.tree.id?'selection-open':''}`}>
    <header className="studio-top"><div className="journey-file"><button className="journey-home" aria-label="Back to your pages" onClick={()=>{if(moduleDirty&&!window.confirm('Discard unsaved website module settings?'))return;if(sharedDirty){setPanel('chrome');return;}if(history&&dirty&&!window.confirm('Leave without saving this page? Your last saved version will stay.'))return;onHome?.()}}>‹</button><div className="document-title"><button className="page-title-button" disabled={!page||busy||conflict||page.published} title={page?.published?'Title editing is limited to unpublished drafts. Published title separation is not supported yet.':'Edit the title of this unpublished page'} aria-label="Edit page title" onClick={()=>{setTitleValue(titles[lang]??'');setTitleLanguage(lang);setTitleError('');setTitleOpen(!titleOpen)}}>{titles[lang]??page?.slug??'Opening your page'} <span aria-hidden="true">✎</span></button><small><i/> Test workspace <span>·</span> Draft</small></div></div><div className="journey-history"><button aria-label="Undo" title="Undo last change" disabled={!history?.past.length} onClick={()=>history&&setHistory(nativeUndo(history))}>↶</button><button aria-label="Redo" title="Redo change" disabled={!history?.future.length} onClick={()=>history&&setHistory(nativeRedo(history))}>↷</button></div><div className="top-actions"><span className="simple-save-state" role="status">{error?'Page unavailable':conflict?'Not saved, page changed':busy?'Saving…':!history?'Opening…':sharedDirty?'Design has unsaved changes':!dirty?'All changes saved':'Unsaved changes'}</span><button className="journey-preview" aria-pressed={previewOnly} onClick={()=>setPreviewOnly(!previewOnly)}>{previewOnly?'Back to editor':'Preview'}</button><button disabled={!history||busy||conflict||titleOpen} className="save" title="Save this page draft. Site design has its own save." onClick={save}>{busy?'Saving…':sharedDirty?'Save page only':'Save changes'}</button></div></header>
    {titleOpen&&<form className="page-title-editor" onSubmit={e=>{e.preventDefault();try{setTitles(updatedPageTitles(titles,titleLanguage,titleValue));setTitleOpen(false)}catch(e){setTitleError(e instanceof Error?e.message:'Check the title.')}}}><label>Page title · {titleLanguage}<input aria-label="Page title for selected language" value={titleValue} maxLength={120} onChange={e=>{setTitleValue(e.target.value);setTitleError('')}} autoFocus disabled={busy||conflict}/></label><p>Changes only this page's title in {titleLanguage}. Address and heading stay unchanged. Use Save changes to keep it. Undo/redo changes canvas content, not this title.</p>{titleError&&<p role="alert">{titleError}</p>}<button type="submit" disabled={busy||conflict}>Use title</button><button type="button" onClick={()=>setTitleOpen(false)}>Cancel</button></form>}
    <div className={`studio-notice ${/failed|refused|Newer|unverified/i.test(notice)?'important-notice':'routine-notice'}`} role="status">{notice}</div>
    {conflict&&<div className="native-conflict" role="alert"><strong>Server page changed. Your edits stay here.</strong><p>Saving is paused to avoid overwriting another session. Export your local page (title and tree) before leaving, then reload deliberately to load the server version.</p><button onClick={()=>{if(!history)return;const url=URL.createObjectURL(new Blob([JSON.stringify({tree:history.tree,titles},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='mizan-unsaved-page.json';a.click();URL.revokeObjectURL(url)}}>Export my unsaved page</button></div>}<details className="simple-connection"><summary>Workspace details</summary><div className="persistence-bar"><span title={themeNotice}>{themeNotice}</span><span>{page?`Page: ${page.slug}`:'No writable page'}</span><span>{key&&key===saved?'Backend tree snapshot loaded/saved':'Native edits not saved'}</span><span>Page Save writes only this draft · shared design has a separate all-pages save</span></div></details>
    {error&&<div className="studio-protection" role="alert"><strong>Source protected. Native editing unavailable.</strong>{error} Nothing was saved. The existing prototype safeguards remain unchanged.</div>}<div className="studio-workspace"><nav className="studio-rail" aria-label="Editor tools"><button className={panel==='add'?'active':''} onClick={()=>setPanel(panel==='add'?null:'add')}><span>＋</span>Insert</button><button className={panel==='explorer'?'active':''} onClick={()=>setPanel(panel==='explorer'?null:'explorer')}><span>▤</span>Pages</button><button className={panel==='chrome'?'active':''} onClick={()=>{setChromeTarget({part:'design'});setPanel(panel==='chrome'?null:'chrome')}}><span>◐</span>Style</button><div className="journey-rail-divider"/><button className={panel==='templates'?'active':''} onClick={()=>{setLibraryView('overview');setPanel(panel==='templates'?null:'templates')}}><span>▧</span>Library</button><button className={panel==='layers'?'active':''} onClick={()=>setPanel(panel==='layers'?null:'layers')}><span>▱</span>Layers</button>{node&&node.id!==history?.tree.id&&<button className={panel==='motion'?'active':''} onClick={()=>setPanel(panel==='motion'?null:'motion')}><span>✧</span>Motion</button>}<button className={panel==='connect'?'active':''} onClick={()=>setPanel(panel==='connect'?null:'connect')}><span>⇄</span>Data</button><div className="rail-note">MIZAN<br/>STUDIO</div></nav>
      <aside className="studio-layers" hidden={!panel}><div className="simple-panel-head"><strong>{panel==='add'?'Add to your page':panel==='templates'?'Website assets':panel==='connect'?'Connect website data':panel==='explorer'?'Website pages':panel==='motion'?'Animate element':panel==='chrome'?'Site design':'Page layers'}</strong><button aria-label="Close tools" onClick={()=>setPanel(null)}>×</button></div>{panel==='connect'&&<WebsiteModuleSettings apiBase={apiBase} onDirty={setModuleDirty} onSaved={()=>setDataRevision(v=>v+1)}/>}<NativeChrome apiBase={apiBase} requestedIdentity={designIntent} onPreview={setPreviewTheme} requestedPart={chromeTarget} active={panel==='chrome'} onDirty={setSharedDirty} onSaved={value=>setTheme(value)}/><h2>{page?.titles[lang]??'Loading page'}</h2>{!history&&panel==='explorer'&&<div><p>This page cannot be edited. Open a supported page below.</p><button onClick={async()=>{try{const result=await api.listPages();setRecoveryPages(result.items);setRecoveryError('')}catch{setRecoveryError('Could not load pages. Try again.')}}}>Load workspace pages</button>{recoveryError&&<p role="alert">{recoveryError}</p>}{recoveryPages.map(p=><button className="recovery-page" key={p.id} disabled={p.status==='archived'} onClick={()=>openPage(p.id)}>{p.titles[lang]??p.slug} · {p.status}</button>)}</div>}{history&&<><div className="native-panel-tabs"><button aria-pressed={panel==='add'} onClick={()=>setPanel('add')}>Add</button><button aria-pressed={panel==='layers'} onClick={()=>setPanel('layers')}>Layers</button></div><div hidden={panel!=='add'}><NativeLibrary requestedPreview={assetIntent?.kind==='block'?assetIntent:undefined} mode="blocks" tree={history.tree} theme={theme} lang={lang} pageId={pageId} busy={busy} loadPages={api.listPages} onOpen={openPage} onBlock={preset=>structure({kind:'preset',preset})} onTemplate={template=>{if(!window.confirm('Replace this page body with the template? Page identity and shared site appearance stay unchanged. Undo restores the previous body before leaving.'))return false;structure({kind:'template',template},true);return true;}}/><details className="library-basic"><summary>Individual elements</summary><div className="native-add-tools"><h3>Add elements</h3><p className="hint">Drag to the page, or choose a position with the keyboard.</p><div id="native-add-panel"/></div></details></div>{panel==='motion'&&node&&<div className="motion-controls"><div key={motionReplay+String(node.settings[device]?.animation)} className={`motion-demo mz-animation-${node.settings[device]?.animation??node.settings.desktop?.animation??'none'} mz-animation-speed-${node.settings[device]?.animation_speed??node.settings.desktop?.animation_speed??'normal'} mz-animation-delay-${node.settings[device]?.animation_delay??node.settings.desktop?.animation_delay??'none'}`}>{readableType(node.type)}</div><p className="motion-note">Choose an entrance effect for this element on {device}. The editing canvas stays still. Preview below, motion is saved with the page.</p><div className="motion-options">{['none','fade','rise','slide','zoom'].map(effect=><button key={effect} aria-pressed={(node.settings[device]?.animation??node.settings.desktop?.animation??'none')===effect} onClick={()=>{edit({kind:'setting',id:node.id,device,field:'animation',value:effect});setMotionReplay(n=>n+1)}}>{effect==='none'?'No animation':effect==='rise'?'Gentle rise':effect==='slide'?'Slide in':effect==='zoom'?'Soft zoom':'Fade in'}</button>)}</div>{(['animation_speed','animation_delay'] as const).map(field=><label key={field}>{field==='animation_speed'?'Speed':'Delay'}<select aria-label={field==='animation_speed'?'Animation speed':'Animation delay'} value={String(node.settings[device]?.[field]??node.settings.desktop?.[field]??(field==='animation_speed'?'normal':'none'))} onChange={e=>edit({kind:'setting',id:node.id,device,field,value:e.target.value})}>{(field==='animation_speed'?['quick','normal','slow']:['none','short','long']).map(v=><option key={v}>{v}</option>)}</select></label>)}<button onClick={()=>setMotionReplay(n=>n+1)}>Replay effect</button><p className="motion-note">One entrance per page load. No infinite loops or scroll triggers. Device settings inherit desktop until changed. Reduced-motion preferences turn all effects off and keep content visible.</p></div>}{<div hidden={panel!=='templates'||libraryView!=='overview'}><LibraryOverview tree={history.tree} theme={theme} onPage={id=>{setAssetIntent({kind:'template',id});setLibraryView('pages')}} onBlock={id=>{setAssetIntent({kind:'block',id});setPanel('add')}} onMotion={()=>{if(node&&node.id!==history.tree.id)setPanel('motion');else setNotice('Select an element on the page, then open Animate to apply motion.')}} onDesign={id=>{if(id)setDesignIntent({id});setChromeTarget({part:'design'});setPanel('chrome')}}/></div>}
{panel==='templates'&&libraryView==='pages'&&<button onClick={()=>setLibraryView('overview')}>Back to all library assets</button>}
{(panel==='explorer'||(panel==='templates'&&libraryView==='pages'))&&<NativeLibrary requestedPreview={panel==='templates'&&assetIntent?.kind==='template'?assetIntent:undefined} mode={panel==='explorer'?'explorer':'templates'} tree={history.tree} theme={theme} lang={lang} pageId={pageId} busy={busy} loadPages={api.listPages} onOpen={openPage} onBlock={preset=>structure({kind:'preset',preset})} onTemplate={template=>{if(!window.confirm('Replace this page body with the template? Page identity and shared site appearance stay unchanged. Undo restores the previous body before leaving.'))return false;structure({kind:'template',template},true);return true;}}/>}<div hidden={panel!=='layers'} className="native-outline"><div className="panel-title">LAYERS</div>{(()=>{const render=(n:typeof history.tree,depth:number):React.ReactNode=><div className="native-layer-group" key={n.id}>{n.children?.length?<details open><summary><button data-node-id={n.id} data-node-type={n.type} className={`native-node ${selected===n.id?'active':''}`} style={{paddingInlineStart:8}} onClick={e=>{e.preventDefault();setSelected(n.id);setPanel(null)}}><b>{readableName(n,lang)}</b><small>{readableType(n.type)}</small></button></summary>{n.children.map(c=>render(c,depth+1))}</details>:<button data-node-id={n.id} data-node-type={n.type} className={`native-node ${selected===n.id?'active':''}`} style={{paddingInlineStart:8}} onClick={()=>{setSelected(n.id);setPanel(null)}}><b>{readableName(n,lang)}</b><small>{readableType(n.type)}</small></button>}</div>;return render(history.tree,0)})()}</div></>}</aside>
      <main className="studio-canvas" onClick={e=>{const chrome=(e.target as HTMLElement).closest('.mz-site-header,.mz-site-footer');if(chrome){setChromeTarget({part:chrome.classList.contains('mz-site-footer')?'footer':'header'});setPanel('chrome')}}}><div className="canvas-bar">{previewTheme&&<span className="scope-chip" role="status">Staged design preview · not saved</span>}<span className="canvas-page-name">{previewOnly?'PREVIEW':'CLICK ANYTHING TO EDIT'}</span><div className="device-switch">{(['desktop','tablet','mobile']as const).map(d=><button key={d} aria-pressed={device===d} onClick={()=>setDevice(d)}>{d}</button>)}</div><label><span className="canvas-language-label">Language</span> <select aria-label="Native content language" value={lang} onChange={e=>setLang(e.target.value as 'en'|'ar')}><option value="en">English</option><option value="ar">Arabic</option></select></label></div>{node&&history&&node.id!==history.tree.id&&<div className="context-toolbar" role="toolbar" aria-label="Selected element tools"><strong>{readableType(node.type)}</strong><button className="native-move-handle" aria-label={`Move ${readableType(node.type)}`} style={{touchAction:'none'}} onPointerDown={e=>{e.preventDefault();window.dispatchEvent(new CustomEvent('native-library-drag',{detail:{item:{kind:'node',id:node.id,type:node.type},x:e.clientX,y:e.clientY}}))}}>⠿ Move</button><button onClick={()=>setPanel(null)}>Edit content</button><button onClick={()=>{setPanel(null);requestAnimationFrame(()=>{const el=document.querySelector<HTMLDetailsElement>('.layout-details');if(el){el.open=true;el.scrollIntoView({block:'nearest'})}})}}>Layout</button><span className="context-divider"/><button onClick={()=>structure({kind:'move',id:node.id,direction:-1})}>Earlier</button><button onClick={()=>structure({kind:'move',id:node.id,direction:1})}>Later</button><button aria-label="Deselect element" onClick={()=>setSelected(history.tree.id)}>×</button></div>}{dynamic&&resolved?.key!==resolutionKey&&<p className="dynamic-preview-status" role="status">{dataError||'Resolving dynamic preview...'}</p>}{history&&<div className={`preview-frame ${device}`}><NativeDragCanvas tree={history.tree} selected={selected} onSelect={id=>{setSelected(id);setPanel(null)}} onChange={structure}><TreePreview tree={dynamic?(resolved?.key===resolutionKey?resolved.tree:({...history.tree,children:[]})):history.tree} lang={lang} device={device} theme={previewTheme??theme}/></NativeDragCanvas></div>}</main>
      <aside className="studio-inspector" hidden={!!panel||!node||node.id===history?.tree.id}><div className="simple-panel-head"><strong>{node?readableType(node.type):'Edit'}</strong><button aria-label="Close element settings" onClick={()=>history&&setSelected(history.tree.id)}>×</button></div>{node&&<><p className="scope-hint">Make it yours. Changes apply to this page.</p><details className="native-advanced"><summary>Advanced element details</summary><code className="native-id">{node.id}</code><p>Stable source identity. Not changed by editing.</p></details>{node.type==='heading'&&<>{!node.repeat&&<NativeDataControls node={node} language={lang} discover={api.discoverData} onChange={bindingChange}/>}<NativeRepeatControls key={node.id+lang} node={node} language={lang} discover={api.discoverData} onChange={repeatChange}/></>}<fieldset disabled={!!node.bindings?.content[lang]?.text||!!node.repeat?.content[lang]} style={{border:0,padding:0,margin:0}}><NativeContentControls node={node} lang={lang} onEdit={(field,value)=>edit({kind:'content',id:node.id,lang,field,value})}/></fieldset><details className="simple-more"><summary>Arrange or remove</summary><fieldset className="link-group"><legend>Structure</legend>{childTypes(node.type).map(type=><button className="add-link" key={type} onClick={()=>{if(history)structure({kind:'insert',parentId:node.id,type,id:newNativeId(history.tree)})}}>+ Add {readableType(type)}</button>)}{history&&node.id!==history.tree.id&&<><div className="link-order"><button onClick={()=>structure({kind:'move',id:node.id,direction:-1})}>Move earlier</button><button onClick={()=>structure({kind:'move',id:node.id,direction:1})}>Move later</button></div><button className="native-remove" onClick={()=>{if(window.confirm('Remove this node and all its children from the draft? Undo is available before leaving.'))structure({kind:'remove',id:node.id})}}>Delete element</button></>}</fieldset></details><details className="simple-more layout-details"><summary>Layout and device settings</summary><div className="inspector-divider"/><div className="panel-title">{device.toUpperCase()} SETTINGS</div>{Object.entries(nativeSettingChoices(node.type)).map(([field,choices])=>{const explicit=node.settings[device]?.[field];return <label key={field}>{field}<select aria-label={`Native setting ${field}`} value={explicit===undefined?'__inherit':String(explicit)} onChange={e=>{const value=choices.find(v=>String(v)===e.target.value);if(value!==undefined)edit({kind:'setting',id:node.id,device,field,value})}}><option value="__inherit" disabled>{device==='desktop'?'Not set (renderer default)':'Inherited from desktop'}</option>{choices.map(v=><option key={String(v)} value={String(v)}>{String(v)}</option>)}</select></label>})}<p className="hint">Text uses a small formatting toolbar. Images and links use address fields; media upload is not connected. Unsupported node types block loading, not silently disappear. This is not complete page-format support.</p></details></>}</aside>
    </div>
  </div>;
                                                                                                                                                                                                                                                                                                                                                                                                                                                 }
