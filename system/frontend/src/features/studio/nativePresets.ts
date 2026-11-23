import type { PageNode } from './pagetree';
import { nativeNodes } from './nativeTree';
export type PresetKind='hero'|'story'|'callout';
export function readableType(type:string){return ({section:'Page',columns:'Section',column:'Column',heading:'Heading',text:'Text',image:'Image',button:'Button'} as Record<string,string>)[type]??type;}
export function readableName(node:PageNode,lang='en'):string {
 const c=node.content[lang]??node.content.en??{};
 const raw=node.type==='heading'?c.text:node.type==='text'?c.html:node.type==='button'?c.label:node.type==='image'?c.alt:null;
 return typeof raw==='string'&&raw.trim()?raw.replace(/<[^>]*>/g,'').replace(/\s+/g,' ').slice(0,42):readableType(node.type);
}
export function createPreset(tree:PageNode,kind:PresetKind):PageNode {
 const ids=new Set(nativeNodes(tree).map(n=>n.id));
 const id=()=>{for(let i=0;i<20;i++){const value='n_'+crypto.randomUUID().replace(/-/g,'').slice(0,16);if(!ids.has(value)){ids.add(value);return value;}}throw Error('Could not allocate preset IDs.');};
 const node=(type:string,content:Record<string,unknown>={},settings:PageNode['settings']={},children?:PageNode[]):PageNode=>({id:id(),type,content:Object.keys(content).length?{en:content}:{},settings,...(children?{children}:{})});
 const heading=node('heading',{text:kind==='callout'?'Make your next move':kind==='story'?'A story worth sharing':'Make room for something better'},{desktop:{level:2}});
 const text=node('text',{html:'<p>Your own words go here. Select any element to make this section yours.</p>'});
 const button=node('button',{label:'Explore more',href:'#'},{desktop:{style:'primary'}});
 const copy=node('column',{}, {},[heading,text,button]);
 const media=node('column',{}, {},[node('image',{alt:'Editable decorative form'},{desktop:{art:kind==='story'?'sculpture_alt':'sculpture',rounded:true}})]);
 return node('columns',{}, {desktop:{columns:kind==='callout'?1:2,gap:'l'},mobile:{stack:true}},kind==='callout'?[copy]:kind==='story'?[media,copy]:[copy,media]);
}
