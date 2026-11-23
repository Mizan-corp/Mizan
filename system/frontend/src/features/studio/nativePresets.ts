import type { PageNode } from './pagetree';
import { nativeNodes } from './nativeTree';
export type PresetKind='hero'|'story'|'callout'|'features'|'quote'|'contact';
export type TemplateKind='studio'|'service'|'editorial';
export const blockCatalog: {id:PresetKind;name:string;category:string;description:string}[]=[
{id:'hero',name:'Intro + image',category:'Intros',description:'A headline, introduction, button and editable art.'},
{id:'story',name:'Image + story',category:'Stories',description:'A two-column story with artwork first.'},
{id:'callout',name:'Call to action',category:'Calls to action',description:'A focused message and one clear next step.'},
{id:'features',name:'Three benefits',category:'Features',description:'Three editable columns for your strongest ideas.'},
{id:'quote',name:'Featured quote',category:'Stories',description:'A centered quote with an attribution.'},
{id:'contact',name:'Contact invitation',category:'Calls to action',description:'A contact headline and editable contact-page link.'}];
export const templateCatalog:{id:TemplateKind;name:string;description:string}[]=[
{id:'studio',name:'Independent studio',description:'An intro, studio story, three values and contact section.'},
{id:'service',name:'Creative services',description:'A service introduction, benefits, client quote and enquiry invitation.'},
{id:'editorial',name:'Journal & ideas',description:'A publication introduction, feature story, quote and reading invitation.'}];
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
 if(kind==='features')return node('columns',{}, {desktop:{columns:3,gap:'m'},mobile:{stack:true}},['Thoughtful by design','Made for real life','Room for your ideas'].map((title,i)=>node('column',{}, {desktop:{padding:'s'}},[node('heading',{text:title},{desktop:{level:3}}),node('text',{html:`<p>Benefit ${i+1}: explain what makes your work different, in your own words.</p>`})])));
 if(kind==='quote')return node('columns',{}, {desktop:{columns:1,gap:'m'}},[node('column',{}, {desktop:{align:'center',padding:'m'}},[node('heading',{text:'Good work starts with a different question.'},{desktop:{level:2,align:'center'}}),node('text',{html:'<p>A thought worth sharing. Add your own attribution here.</p>'},{desktop:{align:'center'}})])]);
 if(kind==='contact')return node('columns',{}, {desktop:{columns:1,gap:'m'}},[node('column',{}, {desktop:{padding:'m'}},[node('heading',{text:'Let’s make something meaningful.'},{desktop:{level:2}}),node('text',{html:'<p>Tell visitors how to reach you. Edit the button destination before using it on your website.</p>'}),node('button',{label:'Get in touch',href:'/contact'},{desktop:{style:'secondary'}})])]);
 const heading=node('heading',{text:kind==='callout'?'Make your next move':kind==='story'?'A story worth sharing':'Make room for something better'},{desktop:{level:2}});
 const text=node('text',{html:'<p>Your own words go here. Select any element to make this section yours.</p>'});
 const button=node('button',{label:'Explore more',href:'#'},{desktop:{style:'primary'}});
 const copy=node('column',{}, {},[heading,text,button]);
 const media=node('column',{}, {},[node('image',{alt:'Editable decorative form'},{desktop:{art:kind==='story'?'sculpture_alt':'sculpture',rounded:true}})]);
 return node('columns',{}, {desktop:{columns:kind==='callout'?1:2,gap:'l'},mobile:{stack:true}},kind==='callout'?[copy]:kind==='story'?[media,copy]:[copy,media]);
}

/** Templates replace page-body composition only. The page/root identity and shared site theme remain owned by the existing page. */
export function createTemplate(tree:PageNode,kind:TemplateKind):PageNode {
 if(!templateCatalog.some(t=>t.id===kind))throw Error('Unknown template.');
 const next=structuredClone(tree),reserved=structuredClone(tree);next.children=[];
 const sequence:PresetKind[]=kind==='studio'?['hero','story','features','contact']:kind==='service'?['hero','features','quote','contact']:['hero','story','quote','callout'];
 for(const block of sequence){const section=createPreset(reserved,block);next.children.push(section);reserved.children=[...(reserved.children??[]),section];}
 const copy:Record<TemplateKind,string[]>={studio:['Independent ideas. Thoughtfully made.','We are a small studio with a clear point of view.','A studio built around people'],service:['A fresh perspective for your next project.','We turn complex challenges into clear, useful experiences.','Services that move your work forward'],editorial:['Stories for a more considered life.','An independent journal of ideas, people and everyday discoveries.','The art of paying attention']};
 const all=nativeNodes(next),headings=all.filter(n=>n.type==='heading'),texts=all.filter(n=>n.type==='text');
 headings[0].content.en={text:copy[kind][0]};headings[0].settings.desktop={...headings[0].settings.desktop,level:1};
 texts[0].content.en={html:`<p>${copy[kind][1]}</p>`};if(headings[1])headings[1].content.en={text:copy[kind][2]};
 return next;
  }
