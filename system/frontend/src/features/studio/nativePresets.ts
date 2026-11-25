import {pageRecipes} from './library/pages/recipes';
import type { PageNode } from './pagetree';
import { nativeNodes } from './nativeTree';
export type PresetKind='product_card'|'hero'|'story'|'callout'|'features'|'quote'|'contact'|'hero_center'|'feedback_cards'|'features_split'|'pricing_cards'|'pricing_simple'|'faq_list'|'faq_columns'|'contact_split'|'gallery_pair'|'gallery_grid'|'team_pair'|'team_grid'|'check_list'|'icon_list'|'category_cards';
export type TemplateKind='studio'|'service'|'editorial';
export {blockCatalog} from './library/blocks/catalog';
export const templateCatalog:{id:TemplateKind;name:string;description:string}[]=[
{id:'studio',name:'Independent studio',description:'An intro, studio story, three values and contact section.'},
{id:'service',name:'Creative services',description:'A service introduction, benefits, client quote and enquiry invitation.'},
{id:'editorial',name:'Journal & ideas',description:'A publication introduction, feature story, quote and reading invitation.'}];
export function readableType(type:string){return ({section:'Page',columns:'Section',column:'Column',heading:'Heading',text:'Text',image:'Image',button:'Button',icon_list:'Icon list',icon:'Icon'} as Record<string,string>)[type]??type;}
export function readableTypeAr(type:string){return ({section:'صفحة',columns:'قسم',column:'عمود',heading:'عنوان',text:'نص',image:'صورة',button:'زر',icon_list:'قائمة أيقونات',icon:'أيقونة'} as Record<string,string>)[type]??type;}
export function readableName(node:PageNode,lang='en'):string {
 const c=node.content[lang]??node.content.en??{};
 const raw=node.type==='heading'?c.text:node.type==='text'?c.html:node.type==='button'?c.label:node.type==='image'?c.alt:null;
 return typeof raw==='string'&&raw.trim()?raw.replace(/<[^>]*>/g,'').replace(/\s+/g,' ').slice(0,42):readableType(node.type);
}
export function createPreset(tree:PageNode,kind:PresetKind):PageNode {
 const ids=new Set(nativeNodes(tree).map(n=>n.id));
 const id=()=>{for(let i=0;i<20;i++){const value='n_'+crypto.randomUUID().replace(/-/g,'').slice(0,16);if(!ids.has(value)){ids.add(value);return value;}}throw Error('Could not allocate preset IDs.');};
 const node=(type:string,content:Record<string,unknown>={},settings:PageNode['settings']={},children?:PageNode[]):PageNode=>({id:id(),type,content:Object.keys(content).length?{en:content}:{},settings,...(children?{children}:{})});
 const h=(text:string,level=3)=>node('heading',{text},{desktop:{level}});
 const t=(text:string)=>node('text',{html:`<p>${text}</p>`});
 const col=(children:PageNode[],align='start')=>node('column',{}, {desktop:{padding:'s',align}},children);
 const row=(children:PageNode[])=>node('columns',{}, {desktop:{columns:children.length,gap:'m'},mobile:{stack:true}},children);
 const art=(alt:string,alternate=false)=>node('image',{alt},{desktop:{art:alternate?'sculpture_alt':'sculpture',rounded:true}});
 const link=(label:string)=>node('button',{label,href:'/contact'},{desktop:{style:'secondary'}});
 if(kind==='product_card')return row([col([h('Product card template'),t('Display price placeholder, hidden unless explicitly connected'),node('image',{alt:'Product image placeholder'},{desktop:{art:'none',rounded:true}})])]);
 if(kind==='hero_center')return row([col([h('A new way to see your everyday.',1),t('Your headline, your vision. Tell people what you are here to make possible.'),link('Start a conversation'),art('Editable introduction artwork')],'center')]);
 if(kind==='feedback_cards')return row([col([h('“A thoughtful experience from start to finish.”'),t('Sample testimonial. Replace with a real quote you have permission to use.'),t('Customer name · Role')]),col([h('“The detail made all the difference.”'),t('Sample testimonial. Replace before publishing.'),t('Customer name · Role')])]);
 if(kind==='features_split')return row([col([art('Editable benefit illustration',true)]),col([h('One idea. A meaningful difference.',2),t('Describe a clear benefit and show why it matters. Keep the explanation in your own voice.'),link('Learn more')])]);
 if(kind==='pricing_cards')return row(['Starter','Growing','Custom'].map((name,i)=>col([h(name),h(i===2?'Let’s talk':i===1?'$49 / month':'$19 / month',2),t('Sample pricing only. Set your actual terms before use.'),t('Describe what is included. No payments are connected.'),link('Enquire about '+name)])));
 if(kind==='pricing_simple')return row([col([h('One clear offer.',2),h('From $99',2),t('Sample price. Replace with your real offer, currency and terms. No checkout is connected.'),link('Ask about this offer')],'center')]);
 if(kind==='faq_list'||kind==='faq_columns')return row((kind==='faq_list'?[['How does it work?','What should I expect?','How can I get started?']]:[['How does it work?','What should I expect?'],['Can I ask a question?','How can I get started?']]).map(questions=>col(questions.flatMap(q=>[h(q),t('Write a clear, useful answer here. These answers stay visible, not hidden in an accordion.')]))));
 if(kind==='contact_split')return row([col([h('Tell us what you have in mind.',2),t('Add your contact details and what visitors can expect next.'),link('Contact us')]),col([art('Editable contact artwork')])]);
 if(kind==='gallery_pair'||kind==='gallery_grid')return row(Array.from({length:kind==='gallery_pair'?2:3},(_,i)=>col([art('Gallery image '+(i+1),i%2===1),t('Your image caption '+(i+1))])));
 if(kind==='team_pair'||kind==='team_grid')return row(Array.from({length:kind==='team_pair'?2:3},(_,i)=>col([art('Replace with team member portrait '+(i+1),i%2===1),h('Team member '+(i+1)),t('Role · Add a short introduction. Sample profile only.')])));
 if(kind==='check_list')return row([col([h('What is included',2),node('text',{html:'<ul><li>First included point. Replace it with your own.</li><li>Second included point. Make it yours.</li><li>Third included point. Keep each one short.</li></ul>'},{desktop:{variant:'check_list'}})])]);
 if(kind==='icon_list')return row([col([h('Why people choose us',2),node('icon_list',{items:[{icon:'Wrench',text:'First reason. Replace it with your own.'},{icon:'ShieldCheck',text:'Second reason. Make it yours.'},{icon:'Truck',text:'Third reason. Keep each one short.'}]})])]);
 if(kind==='category_cards')return row([1,2,3].map(i=>col([art('Category artwork '+i,i%2===0),h('Category name '+i),t('One short line about this category. Replace it with your own.'),node('button',{label:'Browse category',href:'#'},{desktop:{style:'ghost'}})])));
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
 const sequence=pageRecipes[kind];
 for(const block of sequence){const section=createPreset(reserved,block);next.children.push(section);reserved.children=[...(reserved.children??[]),section];}
 const copy:Record<TemplateKind,string[]>={studio:['Independent ideas. Thoughtfully made.','We are a small studio with a clear point of view.','A studio built around people'],service:['A fresh perspective for your next project.','We turn complex challenges into clear, useful experiences.','Services that move your work forward'],editorial:['Stories for a more considered life.','An independent journal of ideas, people and everyday discoveries.','The art of paying attention']};
 const all=nativeNodes(next),headings=all.filter(n=>n.type==='heading'),texts=all.filter(n=>n.type==='text');
 headings[0].content.en={text:copy[kind][0]};headings[0].settings.desktop={...headings[0].settings.desktop,level:1};
 texts[0].content.en={html:`<p>${copy[kind][1]}</p>`};if(headings[1])headings[1].content.en={text:copy[kind][2]};
 return next;
                                                                                                                                                                                                                                                                                            }
