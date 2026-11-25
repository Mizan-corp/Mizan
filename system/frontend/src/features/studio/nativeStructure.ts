import type { PageNode } from './pagetree';
import { createPreset, createTemplate, type TemplateKind, type PresetKind } from './nativePresets';
import { assertNativeTree, nativeNodes, type NativeHistory } from './nativeTree';

export type StructureEdit = {kind:'template';template:TemplateKind} | {kind:'preset';preset:PresetKind;index?:number} | { kind:'insert'; parentId:string; type:string; id:string; index?:number } | {kind:'remove'; id:string} | {kind:'move'; id:string; direction:-1|1} | {kind:'relocate'; id:string; parentId:string; index:number};
export function childTypes(type:string):string[]{return type==='section'?['columns']:type==='columns'?['column']:type==='column'?['heading','text','image','button','icon']:[];}
function createNode(type:string,id:string):PageNode {
  const content: Record<string,Record<string,unknown>> = type==='heading'?{en:{text:'New heading'}}:type==='text'?{en:{html:'<p>New text</p>'}}:type==='image'?{en:{alt:''}}:type==='button'?{en:{label:'New button',href:'#'}}:{};
  return {id,type,settings:type==='columns'?{desktop:{columns:1}}:{},content,...(['section','columns','column'].includes(type)?{children:[]}: {})};
}
export function changeStructure(state:NativeHistory,edit:StructureEdit):NativeHistory {
  assertNativeTree(state.tree);
  let next=structuredClone(state.tree);const nodes=nativeNodes(next);
  if(edit.kind==='template'){next=createTemplate(next,edit.template);
  }else if(edit.kind==='preset'){
    const index=edit.index??(next.children?.length??0);if(!Number.isInteger(index)||index<0||index>(next.children?.length??0))throw Error('Invalid section drop position.');next.children=[...(next.children??[])];next.children.splice(index,0,createPreset(next,edit.preset));
  }else if(edit.kind==='insert'){
    const parent=nodes.find(n=>n.id===edit.parentId);
    if(!parent)throw Error('This node cannot contain that block.');
    if(nodes.some(n=>n.id===edit.id))throw Error('New ID already exists.');
    // Direct-manipulation wrap: a card, column or content block dropped straight
    // onto a section gets the row (and column) it needs instead of a rejection,
    // so an empty section accepts the first drop as users expect.
    const effType=edit.type==='card'?'column':edit.type;
    if(parent.type==='section'&&(effType==='column'||childTypes('column').includes(effType))){
      const index=edit.index??(parent.children?.length??0);
      if(!Number.isInteger(index)||index<0||index>(parent.children?.length??0))throw Error('Invalid drop position.');
      const row=createNode('columns',newNativeId(next));
      const col=createNode('column',effType==='column'?edit.id:newNativeId(next));
      if(edit.type==='card')col.settings={desktop:{background:'card',padding:'s',rounded:true}};
      if(effType!=='column')col.children=[createNode(effType,edit.id)];
      row.children=[col];row.settings={desktop:{columns:1}};
      parent.children=[...(parent.children??[])];parent.children.splice(index,0,row);
      assertNativeTree(next);return {tree:next,past:[...state.past.slice(-29),state.tree],future:[]};
    }
    if(!childTypes(parent.type).includes(edit.type))throw Error('This node cannot contain that block.');
    if(parent.type==='columns'&&(parent.children?.length??0)>=6)throw Error('At most six columns.');
    const added=createNode(edit.type,edit.id);
    if(edit.type==='columns'){let childId=newNativeId(next);while(childId===edit.id)childId=newNativeId(next);added.children=[createNode('column',childId)];}
    const index=edit.index??(parent.children?.length??0);
    if(!Number.isInteger(index)||index<0||index>(parent.children?.length??0))throw Error('Invalid drop position.');
    parent.children=[...(parent.children??[])];parent.children.splice(index,0,added);
    if(parent.type==='columns')parent.settings={...parent.settings,desktop:{...parent.settings.desktop,columns:parent.children.length}};
  }else if(edit.kind==='relocate'){
    if(edit.id===next.id)throw Error('The page root cannot be moved.');
    const node=nodes.find(n=>n.id===edit.id),source=nodes.find(n=>n.children?.some(c=>c.id===edit.id)),target=nodes.find(n=>n.id===edit.parentId);
    if(!node||!source?.children||!target)throw Error('Incompatible drop target.');
    // The same wrap for moves: a column or content block dragged onto a section
    // lands inside a fresh row (and column) at the drop position.
    if(target.type==='section'&&(node.type==='column'||childTypes('column').includes(node.type))){
      if(nativeNodes(node).some(n=>n.id===target.id))throw Error('A node cannot contain itself.');
      if(!Number.isInteger(edit.index)||edit.index<0||edit.index>(target.children?.length??0))throw Error('Invalid drop position.');
      if(source.type==='columns'&&source.children.length===1)throw Error('Keep at least one column in the source row.');
      const oldIndex=source.children.findIndex(n=>n.id===node.id);source.children.splice(oldIndex,1);
      const row=createNode('columns',newNativeId(next));
      const col=node.type==='column'?node:createNode('column',newNativeId(next));
      if(node.type!=='column')col.children=[node];
      row.children=[col];row.settings={desktop:{columns:1}};
      target.children??=[];target.children.splice(edit.index,0,row);
      if(source.type==='columns')source.settings={...source.settings,desktop:{...source.settings.desktop,columns:source.children.length}};
      assertNativeTree(next);return {tree:next,past:[...state.past.slice(-29),state.tree],future:[]};
    }
    if(!childTypes(target.type).includes(node.type))throw Error('Incompatible drop target.');
    if(nativeNodes(node).some(n=>n.id===target.id))throw Error('A node cannot contain itself.');
    if(!Number.isInteger(edit.index)||edit.index<0||edit.index>(target.children?.length??0))throw Error('Invalid drop position.');
    if(source!==target&&source.type==='columns'&&source.children.length===1)throw Error('Keep at least one column in the source row.');
    if(source!==target&&target.type==='columns'&&(target.children?.length??0)>=6)throw Error('At most six columns.');
    const oldIndex=source.children.findIndex(n=>n.id===node.id);source.children.splice(oldIndex,1);
    const index=source===target&&oldIndex<edit.index?edit.index-1:edit.index;
    target.children??=[];target.children.splice(index,0,node);
    for(const row of [source,target])if(row.type==='columns')row.settings={...row.settings,desktop:{...row.settings.desktop,columns:row.children!.length}};
  }else{
    if(edit.id===next.id)throw Error('The page root cannot be removed or moved.');
    const parent=nodes.find(n=>n.children?.some(child=>child.id===edit.id));
    if(!parent?.children)throw Error('Node not found.');
    const index=parent.children.findIndex(n=>n.id===edit.id);
    if(edit.kind==='remove'){
      if(parent.type==='columns'&&parent.children.length===1)throw Error('Keep at least one column. Remove the row instead.');
      parent.children.splice(index,1);
      if(parent.type==='columns')parent.settings={...parent.settings,desktop:{...parent.settings.desktop,columns:parent.children.length}};
    }else{
      const target=index+edit.direction;if(target<0||target>=parent.children.length)throw Error('Already at the edge.');
      [parent.children[index],parent.children[target]]=[parent.children[target],parent.children[index]];
    }
  }
  assertNativeTree(next);return {tree:next,past:[...state.past.slice(-29),state.tree],future:[]};
}
export function newNativeId(tree:PageNode):string {
  const ids=new Set(nativeNodes(tree).map(n=>n.id));
  for(let attempt=0;attempt<10;attempt++){
    const id='n_'+crypto.randomUUID().replace(/-/g,'').slice(0,16);
    if(!ids.has(id))return id;
  }
  throw Error('Could not allocate a unique node ID.');
      }
