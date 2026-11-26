import {it,expect} from 'vitest';
import {libraryCatalog,catalogProblems} from './catalog';
import {pageRecipes} from './pages/recipes';
import {createTemplate} from '../nativePresets';
import {toPageTree} from '../pagetree';
import {initialProject} from '../model';
it('built-in catalog has a closed acyclic relationship graph and real recipe contents',()=>{const assets=libraryCatalog();expect(catalogProblems(assets)).toEqual([]);for(const [id,sections]of Object.entries(pageRecipes)){const asset=assets.find(a=>a.id==='builtin.page.'+id)!;expect(asset.contains).toEqual(sections.map(s=>'builtin.block.'+s));expect(createTemplate(toPageTree(initialProject),id as keyof typeof pageRecipes).children).toHaveLength(sections.length);for(const child of asset.contains)expect(assets.find(a=>a.id===child)?.usedBy).toContain(asset.id)}});
it('refuses duplicate, unresolved and cyclic dependency graphs',()=>{const assets=libraryCatalog();expect(catalogProblems([...assets,assets[0]]).length).toBeGreaterThan(0);assets[0].requires=['missing.module'];expect(catalogProblems(assets)).toContain('Missing asset: missing.module');assets[0].requires=[assets[1].id];assets[1].uses=[assets[0].id];expect(catalogProblems(assets).some(e=>e.includes('Circular'))).toBe(true)});
it('design records preserve explicit shared-site effect and side-effect scope is not hidden',()=>{const assets=libraryCatalog();expect(assets.filter(a=>a.kind==='palette'||a.kind==='typography').every(a=>a.effect==='shared-site')).toBe(true);expect(assets.filter(a=>a.kind==='page').every(a=>a.effect==='page-body')).toBe(true)});
