import type {PageNode} from './pagetree';
import {validResolvedTree} from './nativeBindings';
/** Selection-only map built after exact render-copy validation. Never changes stored IDs. */
export function nativeProjectionMap(source:PageNode,resolved:PageNode,lang:'en'|'ar'):Record<string,string>{
 if(!validResolvedTree(source,resolved,lang))return {};
 const result:Record<string,string>={};
 const visit=(a:PageNode,b:PageNode)=>{
  result[b.id]=a.id;
  const ac=a.children??[],bc=b.children??[];let index=0;
  for(const child of ac){
   const plan=child.card?.content[lang];
   if(plan){for(const copy of bc){result[copy.id]=child.id;let cursor=0;for(const target of child.children??[]){const actual=copy.children?.[cursor];if(!actual)continue;if((target.id===plan.targets.price||target.id===plan.targets.image)&&actual.type!==target.type)continue;visit(target,actual);cursor++}}return;}
   if(child.repeat?.content[lang]){while(index<bc.length&&bc[index].id!==ac[ac.indexOf(child)+1]?.id){visit(child,bc[index++]);}continue;}
   if(bc[index]?.id===child.id)visit(child,bc[index++]);
  }
 };
 visit(source,resolved);return result;
}
