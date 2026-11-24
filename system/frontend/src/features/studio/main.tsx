import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { createRoot } from 'react-dom/client';
import { DRAFT_KEY, PROFILE_KEY, initialProject, loadDraft, moveSection, safeImage, validateProject, type Device, type Project, type Section } from './model';
import './studio.css';
import NativeStudio from './NativeStudio';
import ChromeInspector from './ChromeInspector';
import { previewPayload, toPageTree, sectionNodePrefix } from './pagetree';
import TreePreview from './treerender';
import { shouldWarnBeforeLeave, browserSaveLabel, backendSaveLabel } from './persistenceState';
import { createOperationGate, snapshotKey, saveResultNotice } from './saveState';
import { choosePage } from './pageIdentity';
import { restoreEditablePage } from './editSession';
import { SiteApiError, applySettings, createSitePagesClient, type PageDetail, type PublicAccess } from './sitePages';

// The local-only backend bridge (vite.studio.config.ts): present only when a developer
// boots a LOOPBACK test API with MIZAN_SITE_API + MIZAN_SITE_TOKEN. Saves through it go
// to that local test database, never to a shared server or the public site.
// Hosted mode: a build with VITE_STUDIO_API set (e.g. '/api') talks to the deployment's own
// system API with the signed-in workspace session (double-submit CSRF, same-origin only).
// Otherwise the local-only loopback bridge exactly as before.
const API_BASE: string = import.meta.env.VITE_STUDIO_API ?? '/__studio/api';
const HOSTED = API_BASE !== '/__studio/api';
const BACKEND_LABEL = HOSTED ? 'the workspace backend' : 'the local test backend';
const api = createSitePagesClient({ baseUrl: API_BASE });
type Conn = { state: 'blocked'; reason: string } | { state: 'checking' } | { state: 'off'; reason: string } | { state: 'on'; page: PageDetail | null };

function Studio() {
  const [project, setProject] = useState<Project>(() => loadDraft(localStorage));
  const baseline = useRef(snapshotKey(project));
  const [browserKey, setBrowserKey] = useState<string | null>(() => {
    try { const raw = localStorage.getItem(DRAFT_KEY); const value: unknown = JSON.parse(raw || 'null'); return validateProject(value) ? snapshotKey(value) : null; } catch { return null; }
  });
  const [storageError, setStorageError] = useState('');
  const currentProject = useRef(project); currentProject.current = project;
  const gate = useRef(createOperationGate());
  const [busy, setBusy] = useState<'save'|'publish'|null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [access, setAccess] = useState<PublicAccess | null>(null);
  const [selected, select] = useState(project.sections[0].id);
  const [device, setDevice] = useState<Device>('desktop');
  const [conn, setConn] = useState<Conn>({ state: 'checking' });
  const [notice, setNotice] = useState(HOSTED ? 'Checking the workspace backend...' : 'Local prototype. Checking for a local test backend...');
  const leaveState = { current: snapshotKey(project), baseline: baseline.current, browserSaved: browserKey, backendSaved: savedKey, backendConnected: conn.state === 'on', busy: !!busy };
  useEffect(() => {
    if (!shouldWarnBeforeLeave(leaveState)) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [leaveState.current, leaveState.baseline, browserKey, savedKey, conn.state, busy]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api.listPages();
        if (cancelled) return;
        // Durable theme/chrome: apply the stored settings before the tree restore so a
        // wiped browser still gets the workspace's saved palette, typeface and radius.
        let base = project; let settingsLoaded = false;
        try {
          const settings = await api.getSettings();
          if (cancelled) return;
          base = applySettings(project, settings.value); settingsLoaded = true;
        } catch { /* settings are additive: a missing record never blocks the page restore */ }
        const choice = choosePage(list.items, new URLSearchParams(window.location.search).get('page'));
        if (choice.kind === 'blocked') { setConn({state:'blocked',reason:choice.reason}); setNotice('No writable backend page selected. Browser copy only.'); return; }
        if (choice.kind === 'new') { setConn({ state: 'on', page: null }); if (base !== project) { baseline.current = snapshotKey(base); setProject(base); } setNotice(HOSTED ? 'Connected to the workspace backend. Publishing an activated page changes what visitors see on the public test host.' : 'Connected to the local test backend. Saves go to its database only, never the public site.'); return; }
        const detail = await api.getPage(choice.id);
        if (cancelled) return;
        const restored = restoreEditablePage(detail, base);
        if (!restored.writable) {
          setConn({ state: 'blocked', reason: restored.reason });
          setNotice('Backend page protected. Showing the browser copy only, not the backend page.');
          return;
        }
        baseline.current = snapshotKey(restored.project);
        setProject(restored.project); setSavedKey(settingsLoaded && (detail.draft_tree || detail.published_tree) ? snapshotKey(restored.project) : null); select(restored.project.sections[0].id);
        setNotice(`Loaded the draft and site settings from ${BACKEND_LABEL}.`);
        const url = new URL(window.location.href); url.searchParams.set('page', detail.id); window.history.replaceState(null, '', url);
        setConn({ state: 'on', page: detail });
      } catch (e) {
        if (cancelled) return;
        const reason = e instanceof SiteApiError && (e.isAuth || e.isForbidden) ? (HOSTED ? 'sign-in required: open the workspace app and sign in first' : 'the local backend refused the session') : (HOSTED ? 'the workspace backend is unreachable' : 'no local test backend is running');
        setConn({ state: 'off', reason });
        setNotice(HOSTED ? `Not connected: ${reason}. Editing continues in this browser only; nothing is saved to the workspace.` : `Local prototype: ${reason}. Saving stays in this browser only.`);
      }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const activePageId = conn.state === 'on' && conn.page ? conn.page.id : null;
  const activePublished = conn.state === 'on' && conn.page ? conn.page.published : false;
  useEffect(() => {
    if (!HOSTED || !activePageId || !activePublished) { setAccess(null); return; }
    let cancelled = false;
    api.getPublicAccess(activePageId).then(a => { if (!cancelled) setAccess(a); }).catch(() => { if (!cancelled) setAccess(null); });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePageId, activePublished]);
  const togglePublic = async () => {
    if (conn.state !== 'on' || !conn.page || gate.current.active) return;
    const target = !access?.enabled;
    if (!window.confirm(target
      ? 'Make this page anonymously reachable on the public test host? Synthetic scope: no business data, no accounts, no checkout. You can make it private again at any time.'
      : 'Make this page private? Anonymous visitors will no longer reach it on the public test host.')) return;
    if (!gate.current.start()) return;
    setBusy('publish');
    try {
      const next = await api.setPublicAccess(conn.page.id, target);
      setAccess(next);
      setNotice(target
        ? `Public on the test host (synthetic scope, no business data): ${next.url ?? 'activation saved'}`
        : 'Public access disabled. The page is no longer anonymously reachable on the test host.');
    } catch (e) {
      setNotice(`Public access change failed (${e instanceof SiteApiError ? e.detail || e.status : 'unreachable'}). The page keeps its previous state.`);
    } finally { gate.current.finish(); setBusy(null); }
  };
  const saveServer = async () => {
    if (conn.state !== 'on' || !gate.current.start()) return;
    const snapshot = structuredClone(project); const key = snapshotKey(snapshot);
    setBusy('save'); setSavedKey(null); setNotice(`Saving a snapshot to ${BACKEND_LABEL}... You can keep editing.`);
    try {
      let page = conn.page;
      if (!page) {
        try {
          page = await api.createPage(snapshot);
        } catch (e) {
          if (!(e instanceof SiteApiError && e.isConflict)) throw e;
          setConn({ state: 'blocked', reason: 'A page with this address already exists. Reload to check whether it can be edited safely.' });
          setNotice('Backend page protected. Your browser copy was not saved over the existing page.');
          return;
        }
      }
      if (!(snapshot.language in page.titles) || Object.keys(page.titles).length !== 1) {
        setConn({state:'blocked',reason:'The preview language does not match this page. Reload to restore its original language before saving.'});
        setNotice('Backend page protected. Language changes were not saved.'); return;
      }
      // Brand changes are global settings, never a rename of the page title or slug.
      page = await api.saveDraft(page.id, snapshot, page.titles);
      const url = new URL(window.location.href); url.searchParams.set('page', page.id); window.history.replaceState(null, '', url);
      setConn({ state: 'on', page });
      // Two separate requests: draft first, settings second. They are NOT atomic, so a
      // settings failure after a successful draft save must be reported as exactly that,
      // never as a whole-save failure and never as a whole-save success.
      try {
        await api.putSettings(snapshot);
        setSavedKey(key);
        setNotice(saveResultNotice(key, snapshotKey(currentProject.current), HOSTED));
      } catch (settingsError) {
        setNotice(`Draft saved, but saving site settings FAILED (${settingsError instanceof SiteApiError ? settingsError.detail || settingsError.status : 'unreachable'}). The saved draft keeps the previous theme on reload; press Save to local backend to retry settings.`);
        return;
      }
    } catch (e) {
      if (e instanceof SiteApiError && (e.isAuth || e.isForbidden)) { setConn({ state: 'off', reason: HOSTED ? 'the workspace session was refused' : 'the local backend refused the session' }); }
      setNotice(HOSTED ? `Save to the workspace failed (${e instanceof SiteApiError ? e.detail || e.status : 'unreachable'}). Browser copy kept.` : `Save to local backend failed (${e instanceof SiteApiError ? e.detail || e.status : 'unreachable'}). Browser copy kept; use Save local draft.`);
    } finally { gate.current.finish(); setBusy(null); }
  };
  const publishServer = async () => {
    if (conn.state !== 'on' || !conn.page || gate.current.active) return;
    const key = snapshotKey(project);
    if (savedKey !== key) { setNotice('Save all current changes successfully before publishing.'); return; }
    if (!window.confirm(HOSTED ? 'Publish the SAVED snapshot on this workspace. If this page has an active public activation, visitors see the update.' : 'Publish the SAVED snapshot to the LOCAL TEST backend only. This does not change any public or production site.')) return;
    if (!gate.current.start()) return;
    setBusy('publish'); setNotice(HOSTED ? 'Publishing the saved snapshot...' : 'Publishing the saved snapshot to the local test database...');
    try {
      const page = await api.publish(conn.page.id);
      setConn({ state: 'on', page });
      setNotice(snapshotKey(currentProject.current) === key
        ? (HOSTED ? 'Saved snapshot published. An active public activation for this page now serves it.' : 'Saved snapshot marked published in the local test database. Nothing was deployed or made public.')
        : (HOSTED ? 'Earlier saved snapshot published. Newer unsaved changes are NOT published.' : 'Earlier saved snapshot marked published in the local test database. Newer local changes are NOT saved or published. Nothing was deployed.'));
    } catch (e) {
      setNotice(`Publish failed (${e instanceof SiteApiError ? e.detail || e.status : 'unreachable'}).`);
    } finally { gate.current.finish(); setBusy(null); }
  };
  const [serverPreview,setServerPreview] = useState<string>('');
  const sharedPreview = async () => {
    if (HOSTED) {
      // Hosted parity snapshot: the deployment's own shared renderer via /api/site/data/preview.
      try {
        const payload = previewPayload(project, device);
        const result = await api.previewData(payload.tree as never, project.language, device);
        setServerPreview(result.html); setNotice('Snapshot from the shared server renderer. Refresh after edits.');
      } catch { setNotice('Shared renderer unavailable or rejected the tree. Local illustration is not server parity.'); }
      return;
    }
    try {const response=await fetch('/__studio/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(previewPayload(project,device))});if(!response.ok)throw Error();setServerPreview(await response.text());setNotice('Snapshot from the shared Python renderer. Refresh after edits.');}catch{setNotice('Shared renderer unavailable or rejected the tree. Local illustration is not server parity.');} };
  const [history, setHistory] = useState<Project[]>([]);
  const current = project.sections.find(s => s.id === selected) || project.sections[0];
  const update = (next: Project) => { setHistory(h => [...h.slice(-29), project]); setProject(next); setNotice('Unsaved local changes'); };
  const change = (values: Partial<Section>) => update({ ...project, sections: project.sections.map(s => s.id === current.id ? { ...s, ...values } : s) });
  const save = () => { if (conn.state === 'checking') return; try { localStorage.setItem(DRAFT_KEY, JSON.stringify(project)); setBrowserKey(snapshotKey(project)); setStorageError(''); setNotice('Saved on this browser only. Reload to verify.'); } catch { setStorageError('Browser save failed. Your edits remain in the editor. Export a copy before leaving.'); setNotice('Browser save failed. Backend save status is unchanged.'); } };
  const profile = () => { try { localStorage.setItem(PROFILE_KEY, JSON.stringify(project)); setNotice('Profile saved locally.'); } catch { setNotice('Profile save failed.'); } };
  const restore = () => { try { const p: unknown = JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null'); if (!validateProject(p)) throw Error(); update(p); select(p.sections[0].id); setNotice('Local profile applied. Save draft to keep it.'); } catch { setNotice('No valid local profile yet.'); } };
  const exportFile = () => { const url = URL.createObjectURL(new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = 'mizan-studio-project.json'; a.click(); URL.revokeObjectURL(url); };
  const previewTree = toPageTree(project);
  const previewTheme = previewPayload(project, device).theme;
  const selectFromPreview = (e: React.MouseEvent) => { const el = (e.target as HTMLElement).closest('[id^="n_"]'); if (!el) return; const hit = project.sections.find(s => el.id.startsWith(sectionNodePrefix(s.id))); if (hit) select(hit.id); };
  const colorStyle = { '--paper': project.colors.background, '--ink': project.colors.foreground, '--accent': project.colors.accent, '--radius': `${project.radius}px`, fontFamily: project.font } as CSSProperties;
  return <div className="studio-root">
    <header className="studio-top"><div className="studio-brand"><b>m.</b><span>Web studio <small>EXPERIMENTAL</small></span></div><span className="project-name">{project.name} <i>Draft</i></span><div className="top-actions" inert={conn.state === 'checking'}><button disabled={conn.state === 'checking' || !history.length} onClick={() => { const last = history.at(-1); if (last) { setProject(last); setHistory(h => h.slice(0,-1)); } }}>Undo</button><button disabled={conn.state === 'checking'} onClick={exportFile}>Export</button><button disabled={conn.state === 'checking'} onClick={sharedPreview}>Shared renderer</button>{conn.state === 'on' && <button disabled={!!busy} className="save" onClick={saveServer}>{busy === 'save' ? 'Saving snapshot...' : (HOSTED ? 'Save to workspace' : 'Save to local backend')}</button>}{conn.state === 'on' && conn.page && <button disabled={!!busy || savedKey !== snapshotKey(project)} title={savedKey !== snapshotKey(project) ? 'Save current changes before publishing' : (HOSTED ? 'Publish the saved snapshot on this workspace' : 'Publish the saved local-test snapshot')} onClick={publishServer}>{busy === 'publish' ? 'Publishing snapshot...' : (HOSTED ? 'Publish' : 'Publish (local test)')}</button>}{HOSTED && conn.state === 'on' && conn.page && conn.page.published && <button disabled={!!busy} title="Synthetic scope: anonymous visitors see content only, never business data" onClick={togglePublic}>{access?.enabled ? 'Make private' : 'Make public'}</button>}<button disabled={conn.state === 'checking'} className="save" onClick={save}>Save local draft</button></div></header>
    <div className="studio-notice" role="status" aria-busy={!!busy}>{notice} {access?.enabled && access.url && <a className="public-link" href={access.url} target="_blank" rel="noreferrer">Public: {access.url}</a>} <span>{conn.state === 'on' ? (HOSTED ? `Workspace backend · page: ${conn.page?.slug ?? 'not created yet'} · publishing an activated page changes the public test host` : `Local test backend only · page: ${conn.page?.slug ?? 'not created yet'} · never the public site`) : 'No server publishing · no customer data'}</span></div>
    <div className="persistence-bar" aria-label="Save status"><span>{browserSaveLabel(snapshotKey(project), browserKey)}</span><span>{backendSaveLabel(snapshotKey(project), savedKey, conn.state === 'on')}</span>{busy && <strong>Operation in progress</strong>}{shouldWarnBeforeLeave(leaveState) && <span className="leave-warning">Leaving may lose edits or interrupt an operation.</span>}</div>
    {storageError && <div className="storage-error" role="alert">{storageError}</div>}
    {conn.state === 'blocked'  && <div className="studio-protection" role="alert"><strong>Backend page is read-only in this prototype.</strong> {conn.reason} Backend save and publish are unavailable. Its data is unchanged. You may edit, save or export the browser copy only. <button className="new-page" onClick={() => { const url = new URL(window.location.href); url.searchParams.set('page', 'new'); window.location.href = url.toString(); }}>Start a new page instead</button></div>}
    {conn.state === 'checking' && <div className="studio-loading" role="status">Loading backend page and settings. Editing is paused to protect your browser copy.</div>}
    <div className="studio-workspace" inert={conn.state === 'checking'}>
      <aside className="studio-layers"><div className="panel-title">PAGE STRUCTURE <span>{project.sections.length}</span></div><h2>{conn.state === 'on' && conn.page ? conn.page.titles[project.language] ?? conn.page.slug : 'Browser page'}</h2><p className="hint">Select a section to edit it.</p>{project.sections.map((s,i) => <div key={s.id} className={`layer ${current.id === s.id ? 'active' : ''}`}><button onClick={() => select(s.id)}><span>▦</span> {i === 0 ? 'Hero' : 'Content'} <small>{s.eyebrow.slice(0,19)}</small></button><div className="layer-tools"><button aria-label={`Move ${s.id} up`} onClick={() => update(moveSection(project,s.id,-1))} disabled={!i}>↑</button><button aria-label={`Move ${s.id} down`} onClick={() => update(moveSection(project,s.id,1))} disabled={i === project.sections.length-1}>↓</button></div></div>)}<button className="add-section" onClick={() => { const s = { ...structuredClone(initialProject.sections[1]), id: `section-${Date.now()}` }; update({ ...project, sections: [...project.sections,s] }); select(s.id); }} disabled={project.sections.length >= 20}>+ Add section</button><div className="layers-bottom"><button onClick={profile}>Save as local profile</button><button onClick={restore}>Apply saved profile</button><label className="import-button">Import project<input type="file" accept="application/json" onChange={async e => { const f=e.target.files?.[0]; if (!f) return; try { if(f.size > 200000) throw Error(); const p:unknown=JSON.parse(await f.text()); if(!validateProject(p)) throw Error(); update(p);select(p.sections[0].id); } catch {setNotice('Import refused: invalid or oversized project.');} e.target.value=''; }} /></label></div></aside>
      <main className="studio-canvas">{serverPreview && <div className="shared-preview"><span className="shared-preview-label">Shared server renderer snapshot, from the same renderer public pages use</span><button onClick={()=>setServerPreview('')}>Close shared snapshot</button><iframe title="Shared Python renderer snapshot" sandbox="" srcDoc={serverPreview}/></div>}<div className="canvas-bar"><span>LIVE LOCAL PREVIEW <small>header/footer of a public page come from the site's saved public settings</small></span><div className="device-switch">{(['desktop','tablet','mobile'] as Device[]).map(d => <button key={d} aria-pressed={device===d} onClick={() => setDevice(d)}>{d}</button>)}</div><span>{device==='desktop'?'Fluid':device==='tablet'?'768px':'390px'}</span></div><div className={`preview-frame ${device}`} style={colorStyle} dir={project.language==='ar'?'rtl':'ltr'} onClick={selectFromPreview}><TreePreview tree={previewTree} lang={project.language} device={device} theme={previewTheme as never} /></div></main>
      <aside className="studio-inspector"><div className="panel-title">SECTION SETTINGS</div><h2>Make it yours</h2><label>Eyebrow<input value={current.eyebrow} maxLength={2000} onChange={e => change({eyebrow:e.target.value})}/></label><label>Heading<textarea value={current.title} maxLength={2000} onChange={e => change({title:e.target.value})}/></label><label>Description<textarea value={current.description} maxLength={2000} onChange={e => change({description:e.target.value})}/></label><label>Button label<input value={current.button} maxLength={2000} onChange={e => change({button:e.target.value})}/></label><label>Image URL (HTTPS)<input value={current.image} placeholder="Empty uses local illustration" onChange={e => change({image:e.target.value})} onBlur={() => {if(current.image && !safeImage(current.image)){change({image:''});setNotice('Image URL refused. Use HTTPS without credentials or markup.');}}}/></label><label className="check"><input type="checkbox" checked={current.reversed} onChange={e => change({reversed:e.target.checked})}/> Reverse layout</label><label className="check"><input type="checkbox" checked={current.visible[device]} onChange={e => change({visible:{...current.visible,[device]:e.target.checked}})}/> Visible on {device}</label><div className="inspector-divider"/><div className="panel-title">GLOBAL STYLE</div><label>Brand name<input value={project.name} maxLength={100} onChange={e => update({...project,name:e.target.value})}/></label><div className="color-fields">{(['background','foreground','accent'] as const).map(k => <label key={k}>{k}<input type="color" aria-label={`${k} color`} value={project.colors[k]} onChange={e => update({...project,colors:{...project.colors,[k]:e.target.value}})}/></label>)}</div><label>Typeface<select value={project.font} onChange={e => update({...project,font:e.target.value})}><option value="sans-serif">Modern sans</option><option value="serif">Editorial serif</option><option value="monospace">Monospace</option></select></label><label>Corner radius · {project.radius}px<input type="range" min="0" max="40" value={project.radius} onChange={e => update({...project,radius:Number(e.target.value)})}/></label><div className="inspector-divider"/><ChromeInspector project={project} onChange={update}/><label>Preview language<select value={project.language} onChange={e => update({...project,language:e.target.value as 'en'|'ar'})}><option value="en">English / LTR</option><option value="ar">Arabic / RTL</option></select></label><p className="hint">The language toggle changes direction only: content is not translated.{HOSTED ? ' Saving and the shared Python renderer run against this workspace backend.' : ' Saving and the shared Python renderer work against the local test backend only.'} Motion, business blocks and any production integration are not connected.</p></aside>
    </div>
  </div>;
}
createRoot(document.getElementById('root')!).render(new URLSearchParams(location.search).get('editor') === 'tree' ? <NativeStudio/> : <Studio />);
