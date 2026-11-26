import { describe, expect, it } from 'vitest';
import { initialProject } from './model';
import { previewPayload, toPageTree } from './pagetree';
describe('temporary studio to shared tree conversion',()=>{
 it('produces layout hierarchy and escaped rich text',()=>{const p=structuredClone(initialProject);p.sections[0].description='<script>x</script>';const t=toPageTree(p);expect(t.type).toBe('section');expect(t.children?.[0].type).toBe('columns');expect(t.children?.[0].children?.[0].type).toBe('column');expect(JSON.stringify(t)).toContain('&lt;script&gt;');});
 it('keeps ids stable across reorder and copies device visibility',()=>{const a=toPageTree(initialProject);const p=structuredClone(initialProject);p.sections.reverse();p.sections[0].visible.mobile=false;const b=toPageTree(p);expect(a.children?.[0].id).toBe(b.children?.[1].id);expect(b.children?.[0].settings.mobile.visible).toBe(false);});
 it('points each CTA at the next section anchor and the last one at the page top',()=>{
  const t=toPageTree(initialProject);
  const rows=t.children!;
  const buttonHref=(row:unknown)=>{const r=row as {children:{children:{type:string;content:Record<string,{href?:string}>}[]}[]};const copy=r.children[0];const bt=copy.children.find(c=>c.type==='button')!;return bt.content.en.href;};
  expect(buttonHref(rows[0])).toBe(`#${rows[1].id}`);
  expect(buttonHref(rows[1])).toBe('#n_root01');
  // Every target resolves to a node id the same tree renders.
  const ids=new Set<string>();const walk=(n:{id:string;children?:unknown[]})=>{ids.add(n.id);(n.children??[]).forEach(c=>walk(c as {id:string;children?:unknown[]}));};walk(t as {id:string;children?:unknown[]});
  for(const row of rows){const href=buttonHref(row)!;expect(ids.has(href.slice(1))).toBe(true);}
 });
 it('maps palette and language into a renderer request',()=>{const x=previewPayload(initialProject,'mobile');expect(x.device).toBe('mobile');expect(x.theme.colors.light.primary).toBe(initialProject.colors.accent);expect(x.theme.typography.family).toBe(initialProject.font);expect(x.theme.shape.radius).toBe(initialProject.radius);});
});

// Cross-language contract check, enabled only when the S2 branch's backend is available.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
it.skipIf(!process.env.MIZAN_SITE_BACKEND)('round-trips an edited, saved project through the actual Python validator/renderer',()=>{
 const project=structuredClone(initialProject);project.sections[0].title='Edited and restored';project.sections[0].description='<img onerror="x">';project.sections[1].visible.mobile=false;
 const restored=JSON.parse(JSON.stringify(project));
 const result=spawnSync('python3',[fileURLToPath(new URL('../../../studio-preview.py',import.meta.url))],{input:JSON.stringify(previewPayload(restored,'mobile')),encoding:'utf8',env:process.env});
 expect(result.status,result.stderr).toBe(0);expect(result.stdout).toContain('Edited and restored');expect(result.stdout).not.toContain('Less noise.');expect(result.stdout).not.toContain('<img onerror=');
});
