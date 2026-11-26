import { defaultChrome, validChromeLinks, type Chrome, type ChromeLink, type Project } from './model';

type LinkKind = 'links' | 'actions' | 'footerLinks';

export default function ChromeInspector({ project, onChange }: { project: Project; onChange: (project: Project) => void }) {
  const chrome = project.chrome ?? defaultChrome(project.name);
  const setChrome = (next: Chrome) => onChange({ ...project, chrome: next });
  const editor = (kind: LinkKind, title: string, max: number, description: string) => {
    const entries = chrome[kind] ?? [];
    const replace = (next: ChromeLink[]) => setChrome({ ...chrome, [kind]: next });
    return <fieldset className="link-group">
      <legend>{title} <span>{entries.length}/{max}</span></legend>
      <p className="link-help">{description}</p>
      {entries.length === 0 && <p className="link-empty">No links yet.</p>}
      {entries.map((link, i) => {
        const invalid = !validChromeLinks([link], 1);
        return <div className="link-row" key={i}>
          <div className="link-row-title"><b>Link {i + 1}</b><button type="button" className="remove-link" aria-label={`remove ${kind} ${i + 1}`} onClick={() => replace(entries.filter((_, j) => j !== i))}>Remove</button></div>
          <label>Label<input aria-label={`${kind} label ${i + 1}`} value={link.label} maxLength={40} placeholder="e.g. Our story" onChange={e => replace(entries.map((x, j) => j === i ? { ...x, label: e.target.value } : x))}/></label>
          <label>Destination<input aria-label={`${kind} link ${i + 1}`} value={link.href} maxLength={200} placeholder="/about, #section or https://..." aria-invalid={invalid} onChange={e => replace(entries.map((x, j) => j === i ? { ...x, href: e.target.value } : x))}/></label>
          {invalid && <p className="link-error" role="status">Use a label and a destination starting with /, # or https://.</p>}
          <div className="link-order"><button type="button" disabled={i === 0} aria-label={`Move ${kind} ${i + 1} up`} onClick={() => { const next = [...entries]; [next[i - 1], next[i]] = [next[i], next[i - 1]]; replace(next); }}>Move up</button><button type="button" disabled={i === entries.length - 1} aria-label={`Move ${kind} ${i + 1} down`} onClick={() => { const next = [...entries]; [next[i + 1], next[i]] = [next[i], next[i + 1]]; replace(next); }}>Move down</button></div>
        </div>;
      })}
      <button type="button" className="add-link" disabled={entries.length >= max} onClick={() => replace([...entries, { label: 'New link', href: '#' }])}>+ Add {title.toLowerCase().replace(/s$/, '')}</button>
    </fieldset>;
  };
  return <section className="chrome-inspector" aria-label="Header and footer settings">
    <div className="panel-title">HEADER &amp; FOOTER</div>
    <p className="chrome-scope">Site-wide settings <span>Shared by every page in this workspace when saved to the backend.</span></p>
    {editor('links', 'Header links', 8, 'The main navigation across your site.')}
    {editor('actions', 'Header actions', 4, 'Secondary links beside the navigation.')}
    <fieldset className="link-group"><legend>Footer text</legend><p className="link-help">Up to 4 lines, 120 characters each.</p><label>One line per row<textarea aria-label="footer lines" value={chrome.footer.join('\n')} onChange={e => setChrome({ ...chrome, footer: e.target.value.split('\n').slice(0, 4).map(x => x.slice(0, 120)) })}/></label></fieldset>
    {editor('footerLinks', 'Footer links', 8, 'Useful links such as delivery, returns and contact.')}
  </section>;
}
