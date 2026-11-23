import { createPortal } from 'react-dom';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { PageNode } from './pagetree';
import { readableType, readableName } from './nativePresets';
import { nativeNodes } from './nativeTree';
import { childTypes, newNativeId, type StructureEdit } from './nativeStructure';

type Pick={kind:'new';type:string}|{kind:'node';id:string;type:string}|{kind:'preset';type:'columns';preset:import('./nativePresets').PresetKind}|{kind:'template';type:'columns';template:import('./nativePresets').TemplateKind};
type Drop={parentId:string;index:number;x:number;y:number;width:number;height:number;label:string;box:{x:number;y:number;width:number;height:number}};
type Feedback={x:number;y:number;label:string;sample:string;valid:boolean;destination:string};
export default function NativeDragCanvas({tree,selected,onSelect,onChange,children}:{tree:PageNode;selected:string;onSelect:(id:string)=>void;onChange:(edit:StructureEdit)=>void;children:ReactNode}){
 const canvas=useRef<HTMLDivElement>(null),[pick,setPick]=useState<Pick|null>(null),[drop,setDrop]=useState<Drop|null>(null),[feedback,setFeedback]=useState<Feedback|null>(null),[status,setStatus]=useState('Drag a block to the page. On touch, select an element and use Move. Keyboard users can choose Insert here.');
 const [hover,setHover]=useState('');
 const [paletteHost,setPaletteHost]=useState<HTMLElement|null>(null);useEffect(()=>{setPaletteHost(document.getElementById('native-add-panel'))},[]);
 const active=useRef<Pick|null>(null),destination=useRef<Drop|null>(null),origin=useRef<{x:number;y:number}|null>(null),point=useRef<{x:number;y:number}|null>(null),dragging=useRef(false),suppressClick=useRef(false);
 const nodes=nativeNodes(tree),selectedNode=nodes.find(n=>n.id===selected);
 const ancestors:PageNode[]=[];const findPath=(n:PageNode):boolean=>{ancestors.push(n);if(n.id===selected)return true;for(const c of n.children??[])if(findPath(c))return true;ancestors.pop();return false};findPath(tree);
 useEffect(()=>{const root=canvas.current;if(!root)return;for(const el of root.querySelectorAll<HTMLElement>('.mz-node')){el.classList.toggle('native-selected-node',el.id===selected&&selected!==tree.id);el.classList.toggle('native-hover-node',el.id===hover);el.dataset.nativeType=readableType(nodes.find(n=>n.id===el.id)?.type??'');}},[tree,selected,hover]);
 const allowed=(parent:PageNode,item:Pick)=>{
  if(item.kind==='template')return parent.id===tree.id;
  if(item.kind==='preset')return parent.id===tree.id;
  if(!childTypes(parent.type).includes(item.type))return false;
  if(item.kind==='node'){
   const node=nodes.find(n=>n.id===item.id),source=nodes.find(n=>n.children?.some(c=>c.id===item.id));
   if(!node||nativeNodes(node).some(n=>n.id===parent.id))return false;
   if(source?.id!==parent.id&&source?.type==='columns'&&source.children?.length===1)return false;
   if(source?.id!==parent.id&&parent.type==='columns'&&(parent.children?.length??0)>=6)return false;
  }else if(parent.type==='columns'&&(parent.children?.length??0)>=6)return false;
  return true;
 };
 const apply=(item:Pick,target:{parentId:string;index:number})=>{onChange(item.kind==='preset'?{kind:'preset',preset:item.preset,index:target.index}:item.kind==='template'?{kind:'template',template:item.template}:item.kind==='new'?{kind:'insert',type:item.type,id:newNativeId(tree),...target}:{kind:'relocate',id:item.id,...target});setPick(null);setDrop(null);setStatus('Drop processed. Unsaved page change. Undo is available.');};
 const start=(item:Pick,x:number,y:number)=>{active.current=item;origin.current={x,y};point.current={x,y};destination.current=null;dragging.current=false;};
 const begin=(item:Pick,e:React.PointerEvent)=>{if(e.button!==0)return;start(item,e.clientX,e.clientY);e.preventDefault();};
 useEffect(()=>{
  let frame=0;
  const announce=(value:boolean)=>window.dispatchEvent(new CustomEvent('native-drag-state',{detail:value}));
  const library=(event:Event)=>{const d=(event as CustomEvent).detail;if(d&&['preset','template','node'].includes(d.item?.kind))start(d.item,d.x,d.y)};
  const update=()=>{
   const item=active.current,at=point.current,o=origin.current;if(!item||!at||!o)return;
   if(!dragging.current&&Math.hypot(at.x-o.x,at.y-o.y)<6)return;
   if(!dragging.current){dragging.current=true;setPick(item);announce(true);setStatus('Dragging. Release on a highlighted destination. Escape cancels.');}
   const scroller=canvas.current?.closest<HTMLElement>('.studio-canvas');
   if(scroller){const r=scroller.getBoundingClientRect(),top=r.top+55,bottom=Math.min(r.bottom,innerHeight-74);if(at.x>=r.left&&at.x<=r.right){if(at.y>=r.top+60&&at.y<top+15)scroller.scrollTop-=Math.min(16,(top+15-at.y)/3);else if(at.y>bottom-55)scroller.scrollTop+=Math.min(16,(at.y-bottom+55)/3);}}
   let el=document.elementFromPoint(at.x,at.y)?.closest<HTMLElement>('.mz-node')??null,target:Drop|null=null;
   while(el&&canvas.current?.contains(el)){
    const parent=nodes.find(n=>n.id===el!.id);
    if(parent&&allowed(parent,item)){
     const children=(parent.children??[]).map(n=>document.getElementById(n.id)).filter((n):n is HTMLElement=>!!n);
     const css=getComputedStyle(el),horizontal=parent.type==='columns'&&(css.display.includes('flex')?!css.flexDirection.startsWith('column'):(children.length>1&&Math.abs(children[0].getBoundingClientRect().top-children[1].getBoundingClientRect().top)<10));
     const rtl=horizontal&&css.direction==='rtl';let index=children.findIndex(c=>{const r=c.getBoundingClientRect();return horizontal?(rtl?at.x>r.left+r.width/2:at.x<r.left+r.width/2):at.y<r.top+r.height/2});if(index<0)index=children.length;
     const r=el.getBoundingClientRect(),next=children[index]?.getBoundingClientRect(),last=children.at(-1)?.getBoundingClientRect();
     const prevName=parent.children?.[index-1]?readableName(parent.children[index-1]):'',nextName=parent.children?.[index]?readableName(parent.children[index]):'';
     const label=item.kind==='template'?'Replace page body, confirmation required':prevName&&nextName?`Between ${prevName} and ${nextName}`:nextName?`Before ${nextName}`:prevName?`After ${prevName}`:`Inside ${readableType(parent.type)}`;
     target={parentId:parent.id,index,x:horizontal?(rtl?(next?.right??last?.left??r.right):(next?.left??last?.right??r.left)):r.left,y:horizontal?r.top:(next?.top??last?.bottom??r.top),width:horizontal?4:r.width,height:horizontal?r.height:4,label,box:{x:r.left,y:r.top,width:r.width,height:r.height}};break;
    }
    el=el.parentElement?.closest<HTMLElement>('.mz-node')??null;
   }
   destination.current=target;setDrop(target);
   const n=item.kind==='node'?nodes.find(n=>n.id===item.id):null,label=item.kind==='preset'?`${item.preset} section`:item.kind==='template'?`${item.template} page`:readableType(item.type);
   setFeedback({x:Math.min(innerWidth-228,Math.max(8,at.x+18)),y:Math.min(innerHeight-105,Math.max(8,at.y-155)),label,sample:n?readableName(n):item.kind==='template'?'Replace page body':'New editable block',valid:!!target,destination:target?.label??'Cannot drop here. Move onto a compatible area.'});
  };
  const tick=()=>{update();if(active.current)frame=requestAnimationFrame(tick)};
  const move=(e:PointerEvent)=>{if(!active.current)return;point.current={x:e.clientX,y:e.clientY};if(dragging.current||Math.hypot(e.clientX-origin.current!.x,e.clientY-origin.current!.y)>=6){if(e.cancelable)e.preventDefault();if(!frame)frame=requestAnimationFrame(tick)}};
  const reset=()=>{cancelAnimationFrame(frame);frame=0;active.current=null;point.current=null;origin.current=null;destination.current=null;dragging.current=false;setFeedback(null);setDrop(null);announce(false)};
  const end=()=>{const item=active.current,target=destination.current,moved=dragging.current;if(!item)return;suppressClick.current=moved;setTimeout(()=>{suppressClick.current=false},0);reset();if(moved&&target)apply(item,target);else{if(item.kind==='node'&&!moved)onSelect(item.id);if(item.kind!=='new')setPick(null);setStatus(moved?'Drop cancelled. Page unchanged.':'Element selected. Use Move to drag, or choose an Insert here position.');}};
  const cancel=()=>{reset();setPick(null);setStatus('Drag cancelled. Page unchanged.');};
  const key=(e:KeyboardEvent)=>{if(e.key==='Escape')cancel()};
  addEventListener('native-library-drag',library);addEventListener('pointermove',move,{passive:false});addEventListener('pointerup',end);addEventListener('pointercancel',cancel);addEventListener('keydown',key);
  return()=>{cancelAnimationFrame(frame);removeEventListener('native-library-drag',library);removeEventListener('pointermove',move);removeEventListener('pointerup',end);removeEventListener('pointercancel',cancel);removeEventListener('keydown',key)};
 },[tree,selected]);
 return <div className="native-dnd"><div className="native-palette" aria-label="Selection actions">{paletteHost?createPortal(<div className="native-element-grid">{['columns','column','heading','text','image','button'].map(type=><button key={type} style={{touchAction:'none'}} onPointerDown={e=>begin({kind:'new',type},e)} onClick={()=>{if(suppressClick.current)return;setPick({kind:'new',type});setStatus('Choose a compatible Insert here position below.')}}>+ {readableType(type)}</button>)}</div>,paletteHost):null}</div><nav className="native-breadcrumb" aria-label="Selected node ancestors">{ancestors.map((n,i)=><span key={n.id}>{i>0&&' > '}<button aria-current={n.id===selected?'true':undefined} onClick={()=>onSelect(n.id)}>{readableType(n.type)}</button></span>)}</nav><details className="native-help"><summary>How to add or move</summary><p className="native-dnd-status" role="status">{status}</p></details>{pick&&!feedback&&<details className="native-drop-options" open><summary>Choose insertion position for {pick.type}</summary>{nodes.filter(n=>allowed(n,pick)).map(n=><div key={n.id}><b>{readableType(n.type)} · {readableName(n)}</b>{Array.from({length:(n.children?.length??0)+1},(_,index)=><button key={index} onClick={()=>apply(pick,{parentId:n.id,index})}>Insert here, position {index+1} in {readableName(n)}</button>)}</div>)}<button onClick={()=>{setPick(null);setStatus('Move cancelled.')}}>Cancel move</button></details>}<div ref={canvas} className="native-drag-preview" onPointerMove={e=>{if(active.current)return;const el=(e.target as HTMLElement).closest<HTMLElement>('.mz-node');setHover(el?.id??'')}} onPointerLeave={()=>setHover('')} onPointerDown={e=>{const el=(e.target as HTMLElement).closest<HTMLElement>('.mz-node');const n=nodes.find(n=>n.id===el?.id);if(!n)return;if(e.pointerType==='touch'||n.id===tree.id)onSelect(n.id);else begin({kind:'node',id:n.id,type:n.type},e)}}>{children}</div>{feedback&&createPortal(<div className="native-drag-feedback" aria-live="polite"><div className={`native-drag-ghost ${feedback.valid?'valid':'invalid'}`} style={{left:feedback.x,top:feedback.y}}><b>⠿ {feedback.label}</b><span>{feedback.sample}</span><small>{feedback.valid?'✓ '+feedback.destination:'⊘ '+feedback.destination}</small></div>{drop&&<><div className="native-drop-region" style={{left:drop.box.x,top:drop.box.y,width:drop.box.width,height:drop.box.height}}/><div className="native-drop-marker" data-parent-id={drop.parentId} data-insert-index={drop.index} style={{left:drop.x,top:drop.y,width:drop.width,height:drop.height}}><span>{drop.label}</span></div></>}</div>,document.body)}</div>;
      }
