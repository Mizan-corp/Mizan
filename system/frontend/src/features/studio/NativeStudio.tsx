import { useEffect, useRef, useState } from 'react';
import { changeStructure, childTypes, newNativeId, type StructureEdit } from './nativeStructure';
import { readableName, readableType } from './nativePresets';
import NativeDragCanvas from './NativeDragCanvas';
import NativeContentControls from './NativeContentControls';
import { createSitePagesClient, type PageDetail, SiteApiError } from './sitePages';
import { assertNativeTree, nativeTreeKey, nativeChange, nativeNodes, nativeUndo, nativeRedo, nativeSettingChoices, type NativeHistory, type NativeEdit, type NativeDevice } from './nativeTree';
import TreePreview, { type ThemeSpec } from './treerender';
import { createOperationGate } from './saveState';

const api=createSitePagesClient({baseUrl:'/__studio/api'});
export default function NativeStudio(){
  const [history,setHistory]=useState<NativeHistory|null>(null);
  const [page,setPage]=useState<PageDetail|null>(null);
  const [selected,setSelected]=useState('');
  const [panel,setPanel]=useState<'add'|'layers'|null>(null);
  const [lang,setLang]=useState<'en'|'ar'>('en');
  const [device,setDevice]=useState<NativeDevice>('desktop');
  const [notice,setNotice]=useState('Loading an explicit backend page. No browser-project fallback.');
  const [saved,setSaved]=useState('');
  const [busy,setBusy]=useState(false);
  const [theme,setTheme]=useState<ThemeSpec|undefined>();
  const [themeNotice,setThemeNotice]=useState('Loading saved site appearance...');
  const [conflict,setConflict]=useState(false);
  const [error,setError]=useState('');
  const gate=useRef(createOperationGate());
  const current=useRef(history);current.current=history;
  const key=history?nativeTreeKey(history.tree):'';
  useEffect(()=>{
    let cancelled=false;
    (async()=>{
      try{
        const id=new URLSearchParams(location.search).get('page');if(!id)throw Error('Open an explicit ?editor=tree&page=PAGE_ID link.');
        const detail=await api.getPage(id);if(cancelled)return;
        if(detail.id!==id)throw Error('Backend returned a different page identity.');
        if(!/^[0-9a-f]{64}$/.test(detail.edit_token??''))throw Error('Backend has no native conflict-protection token. Update the local backend before editing.');
        if(detail.status==='archived')throw Error('Archived page is read-only.');
        const tree=detail.draft_tree??detail.published_tree;if(!tree)throw Error('This editor needs an existing supported tree.');
        assertNativeTree(tree);
        try {const settings=await api.getSettings();if(cancelled)return;setTheme(structuredClone(settings.value));setThemeNotice('Saved site appearance loaded, read-only. Draft save never writes settings.');}
        catch {if(cancelled)return;setThemeNotice('Saved appearance unavailable. Renderer defaults shown; no settings will be written.');}
        setPage(detail);setHistory({tree:structuredClone(tree),past:[],future:[]});setSaved(nativeTreeKey(tree));setSelected(tree.id);
        setLang(Object.keys(detail.titles).includes('en')?'en':'ar');setNotice('Native tree loaded. IDs, other languages and untouched fields are preserved. Local test backend only.');
      }catch(e){if(!cancelled)setError(e instanceof Error?e.message:'Load failed. Source is protected.');}
    })();return()=>{cancelled=true};
  },[]);
  useEffect(()=>{
    if(!busy&&(!key||key===saved))return;
    const warn=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue=''};
    addEventListener('beforeunload',warn);return()=>removeEventListener('beforeunload',warn);
  },[key,saved,busy]);
  const edit=(operation:NativeEdit)=>{
    if(!history)return;
    try{setHistory(nativeChange(history,operation));setNotice('Unsaved native tree edit. No project reconstruction.');}catch(e){setNotice(`Edit refused: ${e instanceof Error?e.message:'unsupported operation'}`);}
  };
  const structure=(operation:StructureEdit)=>{
    if(!history)return;
    try{const next=changeStructure(history,operation);setHistory(next);if(operation.kind==='insert')setSelected(operation.id);else if(operation.kind==='remove')setSelected(next.tree.id);else if(operation.kind==='preset'){setSelected(next.tree.children!.at(-1)!.id);setPanel('layers');}setNotice('Unsaved structure edit. Existing node IDs retained. Column-count changes are limited to the edited row.');}
    catch(e){setNotice(`Structure edit refused: ${e instanceof Error?e.message:'unsupported operation'}`)}
  };
  const save=async()=>{
    if(!history||!page||conflict||!gate.current.start())return;
    const snapshot=structuredClone(history.tree),snapshotKey=nativeTreeKey(snapshot);setBusy(true);setNotice('Saving native tree snapshot...');
    try{
      const detail=await api.saveTreeDraft(page.id,snapshot,page.edit_token);
      if(!/^[0-9a-f]{64}$/.test(detail.edit_token??'')||detail.status==='archived'||detail.id!==page.id||nativeTreeKey(detail.draft_tree)!==snapshotKey)throw Error('Backend response differs from the submitted tree. Save not verified.');
      setPage(detail);setSaved(snapshotKey);setNotice(nativeTreeKey(current.current?.tree)===snapshotKey?'Native tree draft saved to the local test backend. Titles and site settings were not changed.':'Earlier native snapshot saved. Newer edits remain unsaved.');
    }catch(e){if(e instanceof SiteApiError&&e.isConflict)setConflict(true);setNotice(`Native save failed or unverified: ${e instanceof Error?e.message:'unreachable'}. Editor copy retained.`);}
    finally{gate.current.finish();setBusy(false);}
  };
  const nodes=history?nativeNodes(history.tree):[];
  const node=nodes.find(n=>n.id===selected);
  useEffect(()=>{if(history&&selected!==history.tree.id)document.getElementById(selected)?.scrollIntoView({block:'nearest',inline:'nearest'})},[selected]);
  return <div className={`studio-root native-studio simple-studio canva-studio ${panel?'tools-open':''} ${node&&node.id!==history?.tree.id?'selection-open':''}`}>
    <header className="studio-top"><div className="studio-brand"><b>m.</b><span>Mizan Studio <small>TEST COPY · NOT ONLINE</small></span></div><div className="document-title">{page?.titles[lang]??'Opening website'}<small>Website design</small></div><div className="top-actions"><span className="simple-save-state" role="status">{error?'Page unavailable':conflict?'Not saved: another session changed this page':busy?'Saving...':!history?'Opening page...':key===saved?'Saved to local test copy':'Unsaved changes'}</span><button disabled={!history?.past.length} onClick={()=>history&&setHistory(nativeUndo(history))}>Undo</button><button disabled={!history?.future.length} onClick={()=>history&&setHistory(nativeRedo(history))}>Redo</button><button disabled={!history||busy||conflict} className="save" onClick={save}>{busy?'Saving...':'Save'}</button></div></header>
    <div className={`studio-notice ${/failed|refused|Newer|unverified/i.test(notice)?'important-notice':'routine-notice'}`} role="status">{notice}</div>
    {conflict&&<div className="native-conflict" role="alert"><strong>Server page changed. Your edits stay here.</strong><p>Saving is paused to avoid overwriting another session. Export your local tree before leaving, then reload deliberately to load the server version.</p><button onClick={()=>{if(!history)return;const url=URL.createObjectURL(new Blob([JSON.stringify(history.tree,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='mizan-unsaved-tree.json';a.click();URL.revokeObjectURL(url)}}>Export my unsaved tree</button></div>}<details className="simple-connection"><summary>Test copy, not your live website</summary><div className="persistence-bar"><span title={themeNotice}>{themeNotice}</span><span>{page?`Page: ${page.slug}`:'No writable page'}</span><span>{key&&key===saved?'Backend tree snapshot loaded/saved':'Native edits not saved'}</span><span>No publish or global-settings writes · native tree only</span></div></details>
    {error?<div className="studio-protection" role="alert"><strong>Source protected. Native editing unavailable.</strong>{error} Nothing was saved. The existing prototype safeguards remain unchanged.</div>:<div className="studio-workspace"><nav className="studio-rail" aria-label="Editor tools"><div className="simple-tools"><button className={panel==='add'?'active':''} onClick={()=>setPanel(panel==='add'?null:'add')}>+ Add</button><button className={panel==='layers'?'active':''} onClick={()=>setPanel(panel==='layers'?null:'layers')}>Layers</button></div><button className={!panel&&node&&node.id!==history?.tree.id?'active':''} disabled={!node||node.id===history?.tree.id} onClick={()=>setPanel(null)}>Edit</button><div className="rail-note">Native<br/>website</div></nav>
      <aside className="studio-layers" hidden={!panel}><div className="simple-panel-head"><strong>{panel==='add'?'Add to your page':'Page layers'}</strong><button aria-label="Close tools" onClick={()=>setPanel(null)}>×</button></div><h2>{page?.titles[lang]??'Loading page'}</h2>{history&&<><div className="native-panel-tabs"><button aria-pressed={panel==='add'} onClick={()=>setPanel('add')}>Add</button><button aria-pressed={panel==='layers'} onClick={()=>setPanel('layers')}>Layers</button></div><div hidden={panel!=='add'}><div className="native-add-tools"><h3>Add elements</h3><p className="hint">Drag to the page, or choose a position with the keyboard.</p><div id="native-add-panel"/></div><div className="native-presets"><h3>Ready sections</h3><p>Insert, then change the words, art and layout.</p>{(['hero','story','callout'] as const).map(preset=><button key={preset} onClick={()=>structure({kind:'preset',preset})}><span className={`preset-mini ${preset}`} aria-hidden="true">▰ ▤</span><b>{preset==='hero'?'Intro + image':preset==='story'?'Image + story':'Call to action'}</b><small>Add editable section</small></button>)}</div></div><div hidden={panel!=='layers'} className="native-outline"><div className="panel-title">LAYERS</div>{(()=>{const render=(n:typeof history.tree,depth:number):React.ReactNode=><div className="native-layer-group" key={n.id}>{n.children?.length?<details open><summary><button data-node-id={n.id} data-node-type={n.type} className={`native-node ${selected===n.id?'active':''}`} style={{paddingInlineStart:8}} onClick={e=>{e.preventDefault();setSelected(n.id);setPanel(null)}}><b>{readableName(n,lang)}</b><small>{readableType(n.type)}</small></button></summary>{n.children.map(c=>render(c,depth+1))}</details>:<button data-node-id={n.id} data-node-type={n.type} className={`native-node ${selected===n.id?'active':''}`} style={{paddingInlineStart:8}} onClick={()=>{setSelected(n.id);setPanel(null)}}><b>{readableName(n,lang)}</b><small>{readableType(n.type)}</small></button>}</div>;return render(history.tree,0)})()}</div></>}</aside>
      <main className="studio-canvas"><div className="canvas-bar"><span className="canvas-page-name">{page?.titles[lang]??'Website'}</span><div className="device-switch">{(['desktop','tablet','mobile']as const).map(d=><button key={d} aria-pressed={device===d} onClick={()=>setDevice(d)}>{d}</button>)}</div><label>Content language <select aria-label="Native content language" value={lang} onChange={e=>setLang(e.target.value as 'en'|'ar')}><option value="en">English</option><option value="ar">Arabic</option></select></label></div>{node&&history&&node.id!==history.tree.id&&<div className="context-toolbar" role="toolbar" aria-label="Selected element tools"><strong>{readableType(node.type)}</strong><button onClick={()=>setPanel(null)}>Edit content</button><button onClick={()=>{setPanel(null);requestAnimationFrame(()=>{const el=document.querySelector<HTMLDetailsElement>('.layout-details');if(el){el.open=true;el.scrollIntoView({block:'nearest'})}})}}>Layout</button><span className="context-divider"/><button onClick={()=>structure({kind:'move',id:node.id,direction:-1})}>Earlier</button><button onClick={()=>structure({kind:'move',id:node.id,direction:1})}>Later</button><button aria-label="Deselect element" onClick={()=>setSelected(history.tree.id)}>×</button></div>}{history&&<div className={`preview-frame ${device}`}><NativeDragCanvas tree={history.tree} selected={selected} onSelect={id=>{setSelected(id);setPanel(null)}} onChange={structure}><TreePreview tree={history.tree} lang={lang} device={device} theme={theme}/></NativeDragCanvas></div>}</main>
      <aside className="studio-inspector" hidden={!!panel||!node||node.id===history?.tree.id}><div className="simple-panel-head"><strong>Edit element</strong><button aria-label="Close element settings" onClick={()=>history&&setSelected(history.tree.id)}>×</button></div>{node&&<><h2>{readableType(node.type)}</h2><details className="native-advanced"><summary>Advanced element details</summary><code className="native-id">{node.id}</code><p>Stable source identity. Not changed by editing.</p></details><NativeContentControls node={node} lang={lang} onEdit={(field,value)=>edit({kind:'content',id:node.id,lang,field,value})}/><details className="simple-more"><summary>Arrange or remove</summary><fieldset className="link-group"><legend>Structure</legend>{childTypes(node.type).map(type=><button className="add-link" key={type} onClick={()=>{if(history)structure({kind:'insert',parentId:node.id,type,id:newNativeId(history.tree)})}}>+ Add {readableType(type)}</button>)}{history&&node.id!==history.tree.id&&<><div className="link-order"><button onClick={()=>structure({kind:'move',id:node.id,direction:-1})}>Move earlier</button><button onClick={()=>structure({kind:'move',id:node.id,direction:1})}>Move later</button></div><button className="native-remove" onClick={()=>{if(window.confirm('Remove this node and all its children from the draft? Undo is available before leaving.'))structure({kind:'remove',id:node.id})}}>Remove selected subtree</button></>}</fieldset></details><details className="simple-more layout-details"><summary>Layout and device settings</summary><div className="inspector-divider"/><div className="panel-title">{device.toUpperCase()} SETTINGS</div>{Object.entries(nativeSettingChoices(node.type)).map(([field,choices])=>{const explicit=node.settings[device]?.[field];return <label key={field}>{field}<select aria-label={`Native setting ${field}`} value={explicit===undefined?'__inherit':String(explicit)} onChange={e=>{const value=choices.find(v=>String(v)===e.target.value);if(value!==undefined)edit({kind:'setting',id:node.id,device,field,value})}}><option value="__inherit" disabled>{device==='desktop'?'Not set (renderer default)':'Inherited from desktop'}</option>{choices.map(v=><option key={String(v)} value={String(v)}>{String(v)}</option>)}</select></label>})}<p className="hint">Text uses a small formatting toolbar. Images and links use address fields; media upload is not connected. Unsupported node types block loading, not silently disappear. This is not complete page-format support.</p></details></>}</aside>
    </div>}
  </div>;
                                                                                                                                                                                                                                                                                                                                                                                                                                                 }
