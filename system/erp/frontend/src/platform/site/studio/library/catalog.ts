import {blockCatalog,templateCatalog} from '../nativePresets';
import {pageRecipes} from './pages/recipes';
import {entranceMotion} from './motion/packs';
import {designIdentities} from './design/identities';
export type AssetKind='page'|'block'|'motion'|'palette'|'typography';
export type LibraryAsset={id:string;kind:AssetKind;name:string;description:string;version:string;owner:'platform';source:'built-in';contains:string[];requires:string[];uses:string[];usedBy:string[];effect:'page-body'|'selected-element'|'shared-site';status:'ready'|'preview-only'};
const record=(value:Omit<LibraryAsset,'version'|'owner'|'source'|'usedBy'>):LibraryAsset=>({...value,version:'1.0.0',owner:'platform',source:'built-in',usedBy:[]});
export function libraryCatalog():LibraryAsset[]{
 const items:LibraryAsset[]=[
 ...blockCatalog.map(b=>record({id:'builtin.block.'+b.id,kind:'block',name:b.name,description:b.description,contains:[],requires:[],uses:[],effect:'page-body',status:'ready'})),
 ...templateCatalog.map(p=>record({id:'builtin.page.'+p.id,kind:'page',name:p.name,description:p.description,contains:pageRecipes[p.id].map(b=>'builtin.block.'+b),requires:[],uses:[],effect:'page-body',status:'ready'})),
 record({id:entranceMotion.id,kind:'motion',name:entranceMotion.name,description:'Four finite entrance effects. Respects reduced motion. No scrolling timelines.',contains:[],requires:[],uses:[],effect:'selected-element',status:'ready'}),
 ...designIdentities.flatMap(d=>[
 record({id:d.id+'.palette',kind:'palette',name:d.name,description:'Five coordinated site color tokens. Shared across pages, never ERP account appearance.',contains:[],requires:[],uses:[],effect:'shared-site',status:'ready'}),
 record({id:d.id+'.typography',kind:'typography',name:d.name+' type',description:d.typography.family+' system family. One supported system family. Separate heading/body scales are not supported yet.',contains:[],requires:[],uses:[],effect:'shared-site',status:'ready'})]),
 ];
 for(const item of items)item.usedBy=items.filter(p=>[...p.contains,...p.requires,...p.uses].includes(item.id)).map(p=>p.id);
 return items;
}
export function catalogProblems(items:LibraryAsset[]):string[]{
 const errors:string[]=[],byId=new Map(items.map(i=>[i.id,i]));if(byId.size!==items.length)errors.push('Duplicate asset identity.');
 const visiting=new Set<string>(),done=new Set<string>();
 const visit=(id:string)=>{if(visiting.has(id)){errors.push('Circular asset relationship: '+id);return;}if(done.has(id))return;const item=byId.get(id);if(!item){errors.push('Missing asset: '+id);return;}visiting.add(id);for(const child of [...item.contains,...item.requires,...item.uses])visit(child);visiting.delete(id);done.add(id)};
 for(const item of items){if(item.kind==='page'&&item.contains.some(id=>byId.has(id)&&byId.get(id)!.kind!=='block'))errors.push('Page starters may contain only blocks.');visit(item.id)}return [...new Set(errors)];
}
