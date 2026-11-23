import { useEffect, useState, type CSSProperties } from 'react';
import { createRoot } from 'react-dom/client';
import { DRAFT_KEY, PROFILE_KEY, initialProject, loadDraft, moveSection, safeImage, validateProject, type Device, type Project, type Section } from './model';
import './studio.css';
import ChromeInspector from './ChromeInspector';
import { previewPayload, toPageTree, sectionNodePrefix } from './pagetree';
import TreePreview from './treerender';
import { fromPageTree } from './fromtree';
import { SiteApiError, applySettings, createSitePagesClient, slugFromName, type PageDetail } from './sitePages';

// The local-only backend bridge (vite.studio.config.ts): present only when a developer
// boots a LOOPBACK test API with MIZAN_SITE_API + MIZAN_SITE_TOKEN. Saves through it go
// to that local test database, never to a shared server or the public site.
const api = createSitePagesClient({ baseUrl: '/__studio/api' });
type Conn = { state: 'checking' } | { state: 'off'; reason: string } | { state: 'on'; page: PageDetail | null };

function Studio() {
  const [project, setProject] = useState<Project>(() => loadDraft(localStorage));
  const [selected, select] = useState(project.sections[0].id);
  const [device, setDevice] = useState<Device>('desktop');
  const [conn, setConn] = useState<Conn>({ state: 'checking' });
  const [notice, setNotice] = useState('Local prototype. Checking for a local test backend...');
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api.listPages();
        if (cancelled) return;
        // Durable theme/chrome: apply the stored settings before the tree restore so a
        // wiped browser still gets the workspace's saved palette, typeface and radius.
        let base = project;
        try {
          const settings = await api.getSettings();
          if (cancelled) return;
          base = applySettings(project, settings.value);
        } catch { /* settings are additive: a missing record never blocks the page restore */ }
        const slug = slugFromName(base.name);
        const found = list.items.find(p => p.slug === slug);
        if (!found) { setConn({ state: 'on', page: null }); if (base !== project) { setProject(base); } setNotice('Connected to the local test backend. Saves go to its database only, never the public site.'); return; }
        const detail = await api.getPage(found.id);
        if (cancelled) return;
        const tree = detail.draft_tree ?? detail.published_tree;
        if (tree) {
          try {
            const restored = fromPageTree(tree, base);
            setProject(restored); select(restored.sections[0].id);
            setNotice('Loaded the draft and site settings from the local test backend.');
          } catch {
            setNotice('Local backend draft uses blocks this prototype cannot edit. Left untouched; showing the local draft.');
          }
        } else {
          setNotice('Connected to the local test backend. Saves go to its database only, never the public site.');
        }
        setConn({ state: 'on', page: detail });
      } catch (e) {
        if (cancelled) return;
        const reason = e instanceof SiteApiError && (e.isAuth || e.isForbidden) ? 'the local backend refused the session' : 'no local test backend is running';
        setConn({ state: 'off', reason });
        setNotice(`Local prototype: ${reason}. Saving stays in this browser only.`);
      }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const saveServer = async () => {
    if (conn.state !== 'on') return;
    try {
      let page = conn.page;
      if (!page) {
        try {
          page = await api.createPage(project);
        } catch (e) {
          if (!(e instanceof SiteApiError && e.isConflict)) throw e;
          const list = await api.listPages();
          const found = list.items.find(p => p.slug === slugFromName(project.name));
          if (!found) throw e;
          page = await api.getPage(found.id);
        }
      }
      page = await api.saveDraft(page.id, project);
      setConn({ state: 'on', page });
      // Two separate requests: draft first, settings second. They are NOT atomic, so a
      // settings failure after a successful draft save must be reported as exactly that,
      // never as a whole-save failure and never as a whole-save success.
      try {
        await api.putSettings(project);
        setNotice('Draft and site settings saved to the local test backend (not the public site).');
      } catch (settingsError) {
        setNotice(`Draft saved, but saving site settings FAILED (${settingsError instanceof SiteApiError ? settingsError.detail || settingsError.status : 'unreachable'}). The saved draft keeps the previous theme on reload; press Save to local backend to retry settings.`);
        return;
      }
    } catch (e) {
      if (e instanceof SiteApiError && (e.isAuth || e.isForbidden)) { setConn({ state: 'off', reason: 'the local backend refused the session' }); }
      setNotice(`Save to local backend failed (${e instanceof SiteApiError ? e.detail || e.status : 'unreachable'}). Browser copy kept; use Save local draft.`);
    }
  };
  const publishServer = async () => {
    if (conn.state !== 'on' || !conn.page) return;
    if (!window.confirm('Publish to the LOCAL TEST backend only. This does not change any public or production site.')) return;
    try {
      const page = await api.publish(conn.page.id);
      setConn({ state: 'on', page });
      setNotice('Marked published in the local test database. Nothing was deployed or made public.');
    } catch (e) {
      setNotice(`Publish failed (${e instanceof SiteApiError ? e.detail || e.status : 'unreachable'}).`);
    }
  };
  const [serverPreview,setServerPreview] = useState<string>('');
  const sharedPreview = async () => { try {const response=await fetch('/__studio/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(previewPayload(project,device))});if(!response.ok)throw Error();setServerPreview(await response.text());setNotice('Snapshot from the shared Python renderer. Refresh after edits.');}catch{setNotice('Shared renderer unavailable or rejected the tree. Local illustration is not server parity.');} };
  const [history, setHistory] = useState<Project[]>([]);
  const current = project.sections.find(s => s.id === selected) || project.sections[0];
  const update = (next: Project) => { setHistory(h => [...h.slice(-29), project]); setProject(next); setNotice('Unsaved local changes'); };
  const change = (values: Partial<Section>) => update({ ...project, sections: project.sections.map(s => s.id === current.id ? { ...s, ...values } : s) });
  const save = () => { try { localStorage.setItem(DRAFT_KEY, JSON.stringify(project)); setNotice('Saved on this browser only. Reload to verify.'); } catch { setNotice('Save failed. Export a copy before leaving.'); } };
  const profile = () => { try { localStorage.setItem(PROFILE_KEY, JSON.stringify(project)); setNotice('Profile saved locally.'); } catch { setNotice('Profile save failed.'); } };
  const restore = () => { try { const p: unknown = JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null'); if (!validateProject(p)) throw Error(); update(p); select(p.sections[0].id); setNotice('Local profile applied. Save draft to keep it.'); } catch { setNotice('No valid local profile yet.'); } };
  const exportFile = () => { const url = URL.createObjectURL(new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = 'mizan-studio-project.json'; a.click(); URL.revokeObjectURL(url); };
  const previewTree = toPageTree(project);
  const previewTheme = previewPayload(project, device).theme;
  const selectFromPreview = (e: React.MouseEvent) => { const el = (e.target as HTMLElement).closest('[id^="n_"]'); if (!el) return; const hit = project.sections.find(s => el.id.startsWith(sectionNodePrefix(s.id))); if (hit) select(hit.id); };
  const colorStyle = { '--paper': project.colors.background, '--ink': project.colors.foreground, '--accent': project.colors.accent, '--radius': `${project.radius}px`, fontFamily: project.font } as CSSProperties;
  return <div className="studio-root">
    <header className="studio-top"><div className="studio-brand"><b>m.</b><span>Web studio <small>EXPERIMENTAL</small></span></div><span className="project-name">{project.name} <i>Draft</i></span><div className="top-actions"><button onClick={() => { const last = history.at(-1); if (last) { setProject(last); setHistory(h => h.slice(0,-1)); } }} disabled={!history.length}>Undo</button><button onClick={exportFile}>Export</button><button onClick={sharedPreview}>Shared renderer</button>{conn.state === 'on' && <button className="save" onClick={saveServer}>Save to local backend</button>}{conn.state === 'on' && conn.page && <button onClick={publishServer}>Publish (local test)</button>}<button className="save" onClick={save}>Save local draft</button></div></header>
    <div className="studio-notice" role="status">{notice} <span>{conn.state === 'on' ? `Local test backend only · page: ${conn.page?.slug ?? 'not created yet'} · never the public site` : 'No server publishing · no customer data'}</span></div>
    <div className="studio-workspace">
      <aside className="studio-layers"><div className="panel-title">PAGE STRUCTURE <span>{project.sections.length}</span></div><h2>Home page</h2><p className="hint">Select a section to edit it.</p>{project.sections.map((s,i) => <div key={s.id} className={`layer ${current.id === s.id ? 'active' : ''}`}><button onClick={() => select(s.id)}><span>▦</span> {i === 0 ? 'Hero' : 'Content'} <small>{s.eyebrow.slice(0,19)}</small></button><div className="layer-tools"><button aria-label={`Move ${s.id} up`} onClick={() => update(moveSection(project,s.id,-1))} disabled={!i}>↑</button><button aria-label={`Move ${s.id} down`} onClick={() => update(moveSection(project,s.id,1))} disabled={i === project.sections.length-1}>↓</button></div></div>)}<button className="add-section" onClick={() => { const s = { ...structuredClone(initialProject.sections[1]), id: `section-${Date.now()}` }; update({ ...project, sections: [...project.sections,s] }); select(s.id); }} disabled={project.sections.length >= 20}>+ Add section</button><div className="layers-bottom"><button onClick={profile}>Save as local profile</button><button onClick={restore}>Apply saved profile</button><label className="import-button">Import project<input type="file" accept="application/json" onChange={async e => { const f=e.target.files?.[0]; if (!f) return; try { if(f.size > 200000) throw Error(); const p:unknown=JSON.parse(await f.text()); if(!validateProject(p)) throw Error(); update(p);select(p.sections[0].id); } catch {setNotice('Import refused: invalid or oversized project.');} e.target.value=''; }} /></label></div></aside>
      <main className="studio-canvas">{serverPreview && <div className="shared-preview"><button onClick={()=>setServerPreview('')}>Close shared snapshot</button><iframe title="Shared Python renderer snapshot" sandbox="" srcDoc={serverPreview}/></div>}<div className="canvas-bar"><span>LIVE LOCAL PREVIEW</span><div className="device-switch">{(['desktop','tablet','mobile'] as Device[]).map(d => <button key={d} aria-pressed={device===d} onClick={() => setDevice(d)}>{d}</button>)}</div><span>{device==='desktop'?'Fluid':device==='tablet'?'768px':'390px'}</span></div><div className={`preview-frame ${device}`} style={colorStyle} dir={project.language==='ar'?'rtl':'ltr'} onClick={selectFromPreview}><TreePreview tree={previewTree} lang={project.language} device={device} theme={previewTheme as never} /></div></main>
      <aside className="studio-inspector"><div className="panel-title">SECTION SETTINGS</div><h2>Make it yours</h2><label>Eyebrow<input value={current.eyebrow} maxLength={2000} onChange={e => change({eyebrow:e.target.value})}/></label><label>Heading<textarea value={current.title} maxLength={2000} onChange={e => change({title:e.target.value})}/></label><label>Description<textarea value={current.description} maxLength={2000} onChange={e => change({description:e.target.value})}/></label><label>Button label<input value={current.button} maxLength={2000} onChange={e => change({button:e.target.value})}/></label><label>Image URL (HTTPS)<input value={current.image} placeholder="Empty uses local illustration" onChange={e => change({image:e.target.value})} onBlur={() => {if(current.image && !safeImage(current.image)){change({image:''});setNotice('Image URL refused. Use HTTPS without credentials or markup.');}}}/></label><label className="check"><input type="checkbox" checked={current.reversed} onChange={e => change({reversed:e.target.checked})}/> Reverse layout</label><label className="check"><input type="checkbox" checked={current.visible[device]} onChange={e => change({visible:{...current.visible,[device]:e.target.checked}})}/> Visible on {device}</label><div className="inspector-divider"/><div className="panel-title">GLOBAL STYLE</div><label>Brand name<input value={project.name} maxLength={100} onChange={e => update({...project,name:e.target.value})}/></label><div className="color-fields">{(['background','foreground','accent'] as const).map(k => <label key={k}>{k}<input type="color" aria-label={`${k} color`} value={project.colors[k]} onChange={e => update({...project,colors:{...project.colors,[k]:e.target.value}})}/></label>)}</div><label>Typeface<select value={project.font} onChange={e => update({...project,font:e.target.value})}><option value="sans-serif">Modern sans</option><option value="serif">Editorial serif</option><option value="monospace">Monospace</option></select></label><label>Corner radius · {project.radius}px<input type="range" min="0" max="40" value={project.radius} onChange={e => update({...project,radius:Number(e.target.value)})}/></label><div className="inspector-divider"/><ChromeInspector project={project} onChange={update}/><label>Preview language<select value={project.language} onChange={e => update({...project,language:e.target.value as 'en'|'ar'})}><option value="en">English / LTR</option><option value="ar">Arabic / RTL</option></select></label><p className="hint">The language toggle changes direction only: content is not translated. Saving and the shared Python renderer work against the local test backend only. Motion, business blocks and any production integration are not connected.</p></aside>
    </div>
  </div>;
}
createRoot(document.getElementById('root')!).render(<Studio />);
