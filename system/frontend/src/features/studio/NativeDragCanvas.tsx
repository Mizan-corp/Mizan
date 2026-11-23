import { createPortal } from 'react-dom';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { PageNode } from './pagetree';
import { readableType, readableName } from './nativePresets';
import { nativeNodes } from './nativeTree';
import { childTypes, newNativeId, type StructureEdit } from './nativeStructure';

type Pick={kind:'new';type:string}|{kind:'node';id:string;type:string};
type Drop={parentId:string;index:number;x:number;y:number;width:number};
export default function NativeDragCanvas({tree,selected,onSelect,onChange,children}:{tree:PageNode;selected:string;onSelect:(id:string)=>void;onChange:(edit:StructureEdit)=>void;children:ReactNode}){
 const canvas=useRef<HTMLDivElement>(null),[pick,setPick]=useState<Pick|null>(null),[drop,setDrop]=useState<Drop|null>(null),[status,setStatus]=useState('Drag a block to the preview. Touch: select an element, then drag its Move handle. Keyboard: choose a block, then an Insert here position.');
 const [hover,setHover]=useState('');
 const [paletteHost,setPaletteHost]=useState<HTMLElement|null>(null);useEffect(()=>{setPaletteHost(document.getElementById('native-add-panel'))},[]);
 const active=useRef<Pick|null>(null),destination=useRef<Drop|null>(null),origin=useRef<{x:number;y:number}|null>(null),suppressClick=useRef(false);
 const nodes=nativeNodes(tree),selectedNode=nodes.find(n=>n.id===selected);
 const ancestors:PageNode[]=[];const findPath=(n:PageNode):boolean=>{ancestors.push(n);if(n.id===selected)return true;for(const c of n.children??[])if(findPath(c))return true;ancestors.pop();return false};findPath(tree);
 useEffect(()=>{
  const root=canvas.current;if(!root)return;
  for(const el of root.querySelectorAll<HTMLElement>('.mz-node')){el.classList.toggle('native-selected-node',el.id===selected&&selected!==tree.id);el.classList.toggle('native-hover-node',el.id===hover);el.dataset.nativeType=readableType(nodes.find(n=>n.id===el.id)?.type??'');}
 },[tree,selected,hover]);
 const allowed=(p:PageNode,item:Pick)=>childTypes(p.type).includes(item.type)&&!(item.kind==='node'&&nativeNodes(nodes.find(n=>n.id===item.id)!).some(n=>n.id===p.id));
 const apply=(item:Pick,target:{parentId:string;index:number})=>{onChange(item.kind==='new'?{kind:'insert',type:item.type,id:newNativeId(tree),...target}:{kind:'relocate',id:item.id,...target});setPick(null);setDrop(null);setStatus('Drop processed. Check the edit status above. Undo is available.');};
 const begin=(item:Pick,e:React.PointerEvent)=>{if(e.button!==0)return;active.current=item;origin.current={x:e.clientX,y:e.clientY};destination.current=null;setPick(item);setStatus('Dragging. Compatible drop positions appear over the preview. Escape cancels.');e.preventDefault();};
 useEffect(()=>{
  const move=(e:PointerEvent)=>{const item=active.current;if(!item||!origin.current||Math.hypot(e.clientX-origin.current.x,e.clientY-origin.current.y)<5)return;
   let el=document.elementFromPoint(e.clientX,e.clientY)?.closest<HTMLElement>('.mz-node')??null;
   while(el&&canvas.current?.contains(el)){
    const parent=nodes.find(n=>n.id===el!.id);
    if(parent&&allowed(parent,item)){
     const children=(parent.children??[]).map(n=>document.getElementById(n.id)).filter((n):n is HTMLElement=>!!n);
     const horizontal=parent.type==='columns';let index=children.findIndex(c=>{const r=c.getBoundingClientRect();return horizontal?e.clientX<r.left+r.width/2:e.clientY<r.top+r.height/2});if(index<0)index=children.length;
     const r=el.getBoundingClientRect(),at=children[index]?.getBoundingClientRect(),last=children.at(-1)?.getBoundingClientRect();
     const target={parentId:parent.id,index,x:horizontal?(at?.left??last?.right??r.left):r.left,y:horizontal?r.top:(at?.top??last?.bottom??r.top),width:horizontal?3:r.width};destination.current=target;setDrop(target);return;
    }
    el=el.parentElement?.closest<HTMLElement>('.mz-node')??null;
   }
   destination.current=null;setDrop(null);
  };
  const end=()=>{suppressClick.current=!!destination.current;setTimeout(()=>{suppressClick.current=false},0);const item=active.current,target=destination.current;active.current=null;origin.current=null;destination.current=null;setDrop(null);if(item&&target)apply(item,target);else if(item){if(item.kind==='node')setPick(null);setStatus('Node or block selected. No drop applied. Drag to move, or choose an Insert here position.');}};
  const cancel=()=>{active.current=null;destination.current=null;origin.current=null;setDrop(null);setPick(null);setStatus('Drag cancelled. Page unchanged.');};
  const key=(e:KeyboardEvent)=>{if(e.key==='Escape')cancel()};
  addEventListener('pointermove',move);addEventListener('pointerup',end);addEventListener('pointercancel',cancel);addEventListener('keydown',key);
  return()=>{removeEventListener('pointermove',move);removeEventListener('pointerup',end);removeEventListener('pointercancel',cancel);removeEventListener('keydown',key)};
 });
 return <div className="native-dnd"><div className="native-palette" aria-label="Selection actions">{paletteHost?createPortal(<div className="native-element-grid">{['columns','column','heading','text','image','button'].map(type=><button key={type} style={{touchAction:'none'}} onPointerDown={e=>begin({kind:'new',type},e)} onClick={()=>{if(suppressClick.current){suppressClick.current=false;return;}setPick({kind:'new',type});setStatus('Block selected. Choose a compatible Insert here position below.')}}>+ {readableType(type)}</button>)}</div>,paletteHost):<div>Loading tools...</div>}{selectedNode&&selectedNode.id!==tree.id&&<button style={{touchAction:'none'}} onPointerDown={e=>begin({kind:'node',id:selectedNode.id,type:selectedNode.type},e)} onClick={()=>{if(suppressClick.current){suppressClick.current=false;return;}setPick({kind:'node',id:selectedNode.id,type:selectedNode.type})}}>Move {readableType(selectedNode.type)}</button>}{selectedNode&&selectedNode.id!==tree.id&&<><button onClick={()=>onChange({kind:'move',id:selectedNode.id,direction:-1})}>Earlier</button><button onClick={()=>onChange({kind:'move',id:selectedNode.id,direction:1})}>Later</button></>}</div><nav className="native-breadcrumb" aria-label="Selected node ancestors">{ancestors.map((n,i)=><span key={n.id}>{i>0&&" > "}<button aria-current={n.id===selected?"true":undefined} onClick={()=>onSelect(n.id)}>{readableType(n.type)}</button></span>)}</nav><details className="native-help"><summary>How to add or move</summary><p className="native-dnd-status" role="status">{status}</p></details>{pick&&<details className="native-drop-options"><summary>Keyboard/click drop positions for {pick.type}</summary>{nodes.filter(n=>allowed(n,pick)).map(n=><div key={n.id}><b>{readableType(n.type)} · {readableName(n)}</b>{Array.from({length:(n.children?.length??0)+1},(_,index)=><button key={index} onClick={()=>apply(pick,{parentId:n.id,index})}>Insert here, position {index+1} in {readableName(n)}</button>)}</div>)}<button onClick={()=>{setPick(null);setStatus('Move cancelled.')}}>Cancel move</button></details>}<div ref={canvas} className="native-drag-preview" onPointerMove={e=>{if(active.current)return;const el=(e.target as HTMLElement).closest<HTMLElement>('.mz-node');setHover(el?.id??'')}} onPointerLeave={()=>setHover('')} onPointerDown={e=>{const el=(e.target as HTMLElement).closest<HTMLElement>('.mz-node');const n=nodes.find(n=>n.id===el?.id);if(n){onSelect(n.id);if(e.pointerType!=='touch'&&n.id!==tree.id)begin({kind:'node',id:n.id,type:n.type},e)}}}>{children}</div>{drop&&<div className="native-drop-marker" style={{position:'fixed',left:drop.x,top:drop.y,width:drop.width,height:drop.width===3?60:4,pointerEvents:'none',zIndex:100}}><span>Drop at position {drop.index+1}</span></div>}</div>;
}
