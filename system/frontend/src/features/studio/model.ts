export type Device = 'desktop' | 'tablet' | 'mobile';
export type Language = 'en' | 'ar';
export type Section = { id: string; eyebrow: string; title: string; description: string; button: string; image: string; visible: Record<Device, boolean>; reversed: boolean };
export type ChromeLink = { label: string; href: string };
export type Chrome = { links: ChromeLink[]; actions: ChromeLink[]; footer: string[] };
export const defaultChrome = (name: string): Chrome => ({ links: [{label:'Collections',href:'#collections'},{label:'Our story',href:'#story'}], actions: [{label:'Search',href:'#search'},{label:'Bag (0)',href:'#bag'}], footer: [name,'Made to make it yours.','Prototype preview only'] });
export function validChromeLinks(v: unknown, max: number): v is ChromeLink[] {
  return Array.isArray(v) && v.length <= max && v.every(x => !!x && typeof x.label === 'string' && x.label.trim().length > 0 && x.label.length <= 40 && typeof x.href === 'string' && /^(#|\/|https:\/\/)/.test(x.href) && x.href.length <= 200);
}
export function validChrome(v: unknown): v is Chrome {
  const c = v as Chrome;
  return !!c && validChromeLinks(c.links, 8) && validChromeLinks(c.actions, 4) && Array.isArray(c.footer) && c.footer.length <= 4 && c.footer.every(x => typeof x === 'string' && x.trim().length > 0 && x.length <= 120);
}
export type Project = { version: 1; name: string; language: Language; colors: { background: string; foreground: string; accent: string }; font: string; radius: number; motion: boolean; chrome?: Chrome; sections: Section[] };
export const initialProject: Project = { version: 1, name: 'Northline studio', language: 'en', colors: { background: '#f3f5f2', foreground: '#122c2b', accent: '#c3ed8d' }, font: 'sans-serif', radius: 24, motion: false, sections: [{ id: 'hero-1', eyebrow: 'DESIGNED FOR EVERYDAY', title: 'Better things.\nMade for your space.', description: 'Thoughtfully selected essentials for the way you live. Make room for something worth keeping.', button: 'Explore the collection', image: '', visible: { desktop: true, tablet: true, mobile: true }, reversed: false }, { id: 'story-1', eyebrow: 'A DIFFERENT PERSPECTIVE', title: 'Less noise.\nMore intention.', description: 'Good design starts with a simple idea. Keep what matters, and make it your own.', button: 'Our approach', image: '', visible: { desktop: true, tablet: true, mobile: true }, reversed: true }] };
export const DRAFT_KEY = 'mizan.experimental-studio.v1';
export const PROFILE_KEY = 'mizan.experimental-studio.profiles.v1';
export function validateProject(value: unknown): value is Project {
  try { return checkProject(value); } catch { return false; }
}
function checkProject(value: unknown): value is Project {
  if (!value || typeof value !== 'object') return false;
  const p = value as Project;
  return p.version === 1 && typeof p.name === 'string' && p.name.length <= 100 && ['en','ar'].includes(p.language) && ['sans-serif','serif','monospace'].includes(p.font) && typeof p.motion === 'boolean' && (p.chrome === undefined || validChrome(p.chrome)) && Number.isInteger(p.radius) && p.radius >= 0 && p.radius <= 40 && !!p.colors && Object.keys(p.colors).sort().join(',') === 'accent,background,foreground' && Object.values(p.colors).every(c => typeof c === 'string' && /^#[a-fA-F0-9]{6}$/.test(c)) && Array.isArray(p.sections) && p.sections.length > 0 && p.sections.length <= 20 && new Set(p.sections.map(s => s?.id)).size === p.sections.length && p.sections.every(s => !!s && typeof s.id === 'string' && /^[a-z0-9-]{1,60}$/.test(s.id) && ['eyebrow','title','description','button','image'].every(k => typeof s[k as keyof Section] === 'string' && (s[k as keyof Section] as string).length <= 2000) && (!s.image || safeImage(s.image)) && typeof s.reversed === 'boolean' && !!s.visible && ['desktop','tablet','mobile'].every(d => typeof s.visible[d as Device] === 'boolean'));
}
export function loadDraft(storage: Pick<Storage, 'getItem'>): Project {
  try { const value: unknown = JSON.parse(storage.getItem(DRAFT_KEY) || 'null'); if (validateProject(value)) return value; } catch { /* invalid local drafts do not replace defaults */ }
  return structuredClone(initialProject);
}
export function moveSection(project: Project, id: string, direction: -1 | 1): Project {
  const sections = [...project.sections]; const index = sections.findIndex(s => s.id === id); const next = index + direction;
  if (index < 0 || next < 0 || next >= sections.length) return project;
  [sections[index], sections[next]] = [sections[next], sections[index]];
  return { ...project, sections };
}

export function safeImage(value: string): boolean { try { const u=new URL(value); return u.protocol==='https:' && !!u.hostname && !u.username && !u.password && !/[\\<>\"\s]/.test(value); } catch { return false; } }
