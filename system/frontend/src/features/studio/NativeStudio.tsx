import { useEffect, useRef, useState } from 'react';
import { changeStructure, childTypes, newNativeId, type StructureEdit } from './nativeStructure';
import NativeContentControls from './NativeContentControls';
import { createSitePagesClient, type PageDetail } from './sitePages';
import { assertNativeTree, nativeTreeKey, nativeChange, nativeNodes, nativeUndo, nativeRedo, nativeSettingChoices, type NativeHistory, type NativeEdit, type NativeDevice } from './nativeTree';
import TreePreview, { type ThemeSpec } from './treerender';
import { createOperationGate } from './saveState';

const api=createSitePagesClient({baseUrl:'/__studio/api'});
export default function NativeStudio(){
  const [history,setHistory]=useState<NativeHistory|null>(null);
  const [page,setPage]=useState<PageDetail|null>(null);
  const [selected,setSelected]=useState('');
  const [lang,setLang]=useState<'en'|'ar'>('en');
  const [device,setDevice]=useState<NativeDevice>('desktop');
  const [notice,setNotice]=useState('Loading an explicit backend page. No browser-project fallback.');
  const [saved,setSaved]=useState('');
  const [busy,setBusy]=useState(false);
  const [theme,setTheme]=useState<ThemeSpec|undefined>();
  const [themeNotice,setThemeNotice]=useState('Loading saved site appearance...');
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
    try{const next=changeStructure(history,operation);setHistory(next);if(operation.kind==='insert')setSelected(operation.id);else if(operation.kind==='remove')setSelected(next.tree.id);setNotice('Unsaved structure edit. Existing node IDs retained. Column-count changes are limited to the edited row.');}
    catch(e){setNotice(`Structure edit refused: ${e instanceof Error?e.message:'unsupported operation'}`)}
  };
  const save=async()=>{
    if(!history||!page||!gate.current.start())return;
    const snapshot=structuredClone(history.tree),snapshotKey=nativeTreeKey(snapshot);setBusy(true);setNotice('Saving native tree snapshot...');
    try{
      const detail=await api.saveTreeDraft(page.id,snapshot);
      if(detail.status==='archived'||detail.id!==page.id||nativeTreeKey(detail.draft_tree)!==snapshotKey)throw Error('Backend response differs from the submitted tree. Save not verified.');
      setPage(detail);setSaved(snapshotKey);setNotice(nativeTreeKey(current.current?.tree)===snapshotKey?'Native tree draft saved to the local test backend. Titles and site settings were not changed.':'Earlier native snapshot saved. Newer edits remain unsaved.');
    }catch(e){setNotice(`Native save failed or unverified: ${e instanceof Error?e.message:'unreachable'}. Editor copy retained.`);}
    finally{gate.current.finish();setBusy(false);}
  };
  const nodes=history?nativeNodes(history.tree):[];
  const node=nodes.find(n=>n.id===selected);
  return <div className="studio-root native-studio">
    <header className="studio-top"><div className="studio-brand"><b>m.</b><span>Tree-native studio <small>EXPERIMENTAL SUBSET</small></span></div><div className="top-actions"><button disabled={!history?.past.length} onClick={()=>history&&setHistory(nativeUndo(history))}>Undo</button><button disabled={!history?.future.length} onClick={()=>history&&setHistory(nativeRedo(history))}>Redo</button><button disabled={!history||busy} className="save" onClick={save}>{busy?'Saving native snapshot...':'Save native draft'}</button></div></header>
    <div className="studio-notice" role="status">{notice}</div>
    <div className="persistence-bar"><span title={themeNotice}>{themeNotice}</span><span>{page?`Page: ${page.slug}`:'No writable page'}</span><span>{key&&key===saved?'Backend tree snapshot loaded/saved':'Native edits not saved'}</span><span>No publish or global-settings writes · native tree only</span></div>
    {error?<div className="studio-protection" role="alert"><strong>Source protected. Native editing unavailable.</strong>{error} Nothing was saved. The existing prototype safeguards remain unchanged.</div>:<div className="studio-workspace">
      <aside className="studio-layers"><div className="panel-title">ORIGINAL TREE NODES</div><h2>{page?.titles[lang]??'Loading page'}</h2><p className="hint">Choose a node. Add inside a layout, reorder siblings or remove a selected subtree. Existing IDs stay unchanged.</p>{nodes.map(n=><button className={`native-node ${selected===n.id?'active':''}`} key={n.id} onClick={()=>setSelected(n.id)}><b>{n.type}</b><small>{n.id}</small></button>)}</aside>
      <main className="studio-canvas"><div className="canvas-bar"><div className="device-switch">{(['desktop','tablet','mobile']as const).map(d=><button key={d} aria-pressed={device===d} onClick={()=>setDevice(d)}>{d}</button>)}</div><label>Content language <select aria-label="Native content language" value={lang} onChange={e=>setLang(e.target.value as 'en'|'ar')}><option value="en">English</option><option value="ar">Arabic</option></select></label></div>{history&&<div className={`preview-frame ${device}`} onClick={e=>{const n=(e.target as HTMLElement).closest('.mz-node');if(n)setSelected(n.id)}}><TreePreview tree={history.tree} lang={lang} device={device} theme={theme}/></div>}</main>
      <aside className="studio-inspector"><div className="panel-title">NATIVE NODE EDITS</div>{node&&<><h2>{node.type}</h2><code className="native-id">{node.id}</code><p className="hint">Edits affect only this field, language or device. Other values remain untouched.</p><NativeContentControls node={node} lang={lang} onEdit={(field,value)=>edit({kind:'content',id:node.id,lang,field,value})}/><fieldset className="link-group"><legend>Structure</legend>{childTypes(node.type).map(type=><button className="add-link" key={type} onClick={()=>{if(history)structure({kind:'insert',parentId:node.id,type,id:newNativeId(history.tree)})}}>+ Add {type}</button>)}{history&&node.id!==history.tree.id&&<><div className="link-order"><button onClick={()=>structure({kind:'move',id:node.id,direction:-1})}>Move earlier</button><button onClick={()=>structure({kind:'move',id:node.id,direction:1})}>Move later</button></div><button className="native-remove" onClick={()=>{if(window.confirm('Remove this node and all its children from the draft? Undo is available before leaving.'))structure({kind:'remove',id:node.id})}}>Remove selected subtree</button></>}</fieldset><div className="inspector-divider"/><div className="panel-title">{device.toUpperCase()} SETTINGS</div>{Object.entries(nativeSettingChoices(node.type)).map(([field,choices])=>{const explicit=node.settings[device]?.[field];return <label key={field}>{field}<select aria-label={`Native setting ${field}`} value={explicit===undefined?'__inherit':String(explicit)} onChange={e=>{const value=choices.find(v=>String(v)===e.target.value);if(value!==undefined)edit({kind:'setting',id:node.id,device,field,value})}}><option value="__inherit" disabled>{device==='desktop'?'Not set (renderer default)':'Inherited from desktop'}</option>{choices.map(v=><option key={String(v)} value={String(v)}>{String(v)}</option>)}</select></label>})}<p className="hint">Text uses a small formatting toolbar. Images and links use address fields; media upload is not connected. Unsupported node types block loading, not silently disappear. This is not complete page-format support.</p></>}</aside>
    </div>}
  </div>;
                                                                                                                                                                                                                                                                                                                                                                                                                                                 }
