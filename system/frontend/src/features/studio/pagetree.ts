import { defaultChrome, type Project } from './model';
export type PageNode = { id: string; type: string; settings: Record<string, Record<string, string | number | boolean>>; content: Record<string, Record<string, unknown>>; children?: PageNode[]; bindings?:import('./nativeBindings').NativeBindings; repeat?:import('./nativeBindings').NativeRepeat; card?:import('./nativeCards').NativeCard };
// One conversion path for preview/export. IDs are deterministic and remain stable across edits.
export function toPageTree(project: Project): PageNode {
 const lang = project.language;
 const node = (id:string,type:string,content:Record<string,unknown>={},settings:PageNode['settings']={},children?:PageNode[]):PageNode => ({id,type,settings,content:Object.keys(content).length?{[lang]:content}:{},...(children?{children}:{})});
 return node('n_root01','section',{}, {desktop:{padding:'l',max_width:'wide'},mobile:{padding:'m'}}, project.sections.map((section, index)=> {
  const id = hash(section.id);
  // The CTA scrolls to the next section, or back to the page top from the last
  // one: every published anchor resolves to a node id this same tree renders,
  // so the button behaves identically in the local preview and on a public page.
  const next = project.sections[index + 1];
  const cta = next ? `#n_${hash(next.id)}rw` : '#n_root01';
  if (section.kind === 'features') {
   // Feature cards: a lead copy column (eyebrow, heading, intro) plus one column per
   // card (level-3 heading + text). No button/note/image nodes; fromtree relies on
   // that shape difference to tell this row apart from a split row, fail closed.
   const lead = node(`n_${id}cp`,'column',{}, {}, [
    node(`n_${id}eb`,'text',{html:`<p>${escape(section.eyebrow)}</p>`},{desktop:{variant:'eyebrow'}}),
    node(`n_${id}hd`,'heading',{text:section.title},{desktop:{level:2}}),
    node(`n_${id}tx`,'text',{html:`<p>${escape(section.description)}</p>`}),
   ]);
   const cards = (section.cards ?? []).slice(0, 4).map((card, ci) => node(`n_${id}c${ci}`,'column',{}, {desktop:{background:'card',rounded:true,padding:'m'}}, [
    node(`n_${id}c${ci}h`,'heading',{text:card.title},{desktop:{level:3}}),
    node(`n_${id}c${ci}t`,'text',{html:`<p>${escape(card.text)}</p>`}),
   ]));
   const count = 1 + cards.length;
   return node(`n_${id}rw`,'columns',{}, {desktop:{columns:count,visible:section.visible.desktop,gap:'l'},tablet:{visible:section.visible.tablet,columns:Math.min(count,2)},mobile:{visible:section.visible.mobile,stack:true}},[lead,...cards]);
  }
  const copy = node(`n_${id}cp`,'column',{}, {}, [
   node(`n_${id}eb`,'text',{html:`<p>${escape(section.eyebrow)}</p>`},{desktop:{variant:'eyebrow'}}),
   node(`n_${id}hd`,'heading',{text:section.title},{desktop:{level:1}}),
   node(`n_${id}tx`,'text',{html:`<p>${escape(section.description)}</p>`}),
   node(`n_${id}bt`,'button',{label:section.button,href:cta},{desktop:{style:'primary'}}),
   node(`n_${id}nt`,'text',{html:`<p>${escape(String(index+1).padStart(2,'0'))} / INTENTIONAL BY DESIGN</p>`},{desktop:{variant:'note'}}),
  ]);
  // The two-column composition (copy + media) is part of the design, with or without a
  // photo: an empty image keeps its column as registered decorative art, never dropped.
  const art = section.image ? 'none' : (index % 2 ? 'sculpture_alt' : 'sculpture');
  const imageContent = section.image ? {src:section.image,alt:''} : {alt:''};
  const image = node(`n_${id}im`,'column',{}, {}, [node(`n_${id}ph`,'image',imageContent,{desktop:{rounded:true,art}})]);
  // Child order stays copy-first; reversal is a desktop-only presentation setting so
  // stacked devices keep the copy-first reading order for every section.
  return node(`n_${id}rw`,'columns',{}, {desktop:{columns:2,visible:section.visible.desktop,gap:'l',reverse:section.reversed},tablet:{visible:section.visible.tablet},mobile:{visible:section.visible.mobile,stack:true,reverse:false}},[copy,image]);
 }));
}
function escape(value:string):string { return value.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!)); }
export function previewPayload(project:Project,device:string) {
 const chrome=project.chrome??defaultChrome(project.name);
 return {tree:toPageTree(project),lang:project.language,device,meta:{titles:{[project.language]:project.name}},theme:{colors:{light:{background:project.colors.background,foreground:project.colors.foreground,primary:project.colors.accent,'primary-foreground':project.colors.foreground}},typography:{family:project.font},shape:{radius:project.radius},header:{brand:project.name,links:chrome.links.filter(l=>l.label.trim()),actions:chrome.actions.filter(l=>l.label.trim())},footer:{lines:chrome.footer.filter(x=>x.trim()),...(chrome.footerLinks !== undefined ? {links:chrome.footerLinks.filter(l=>l.label.trim())} : {})}}};
}

// Maps a Project section to the deterministic id prefix of its tree nodes (click-to-select in the studio).
export function sectionNodePrefix(id: string): string { return `n_${hash(id)}`; }
function hash(value:string):string { let h=2166136261;for(const c of value){h=Math.imul(h^c.charCodeAt(0),16777619);}return (h>>>0).toString(36).padStart(7,'0'); }
