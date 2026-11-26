import type {PageNode} from './pagetree';
export type NewPageInput={title:string;slug:string;language:'en'|'ar'};
export function newPagePayload(input:NewPageInput):{slug:string;titles:Record<string,string>;tree:PageNode}{
 const title=input.title.trim(),slug=input.slug.trim();
 if(!title||title.length>120)throw Error('Use a page title between 1 and 120 characters.');
 if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)||slug.length>80)throw Error('Use up to 80 lowercase letters, numbers and single hyphens for the page address.');
 if(!['en','ar'].includes(input.language))throw Error('Choose English or Arabic.');
 const id=()=>`n_${crypto.randomUUID().replace(/-/g,'').slice(0,16)}`;
 const node=(type:string,children?:PageNode[]):PageNode=>({id:id(),type,settings:{},content:{},...(children?{children}:{})});
 const heading=node('heading');heading.settings={desktop:{level:1}};heading.content={[input.language]:{text:title}};
 return {slug,titles:{[input.language]:title},tree:node('section',[node('columns',[node('column',[heading])])])};
}
