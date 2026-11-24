// Abstract library thumbnails per the approved visual concept: schematic minis in
// the approved sand/teal tokens, not scaled real page content. Selecting an asset
// still opens its real full-size preview, so the card stays a honest map marker.
export default function MiniThumb({id,kind}:{id:string;kind:'block'|'page'}){
 const s=/hero|header|banner/.test(id)?'hero':/gallery|grid|feature|product|card|menu/.test(id)?'grid':/image|media|story|about/.test(id)?'pic':/quote|callout|testimonial/.test(id)?'lines':/contact|form|newsletter|footer/.test(id)?'form':'hero';
 return <div className="mz-thumb" aria-hidden="true" data-mini={s}><div className="mz-mini">
  {kind==='page'&&<div className="mz-mnav"><div className="mz-mlogo"/><div className="mz-mlinks"><i/><i/><i/></div></div>}
  {s==='hero'&&<div className="mz-mhero"><div className="l1"/><div className="l2"/><div className="cta"/>{kind==='page'&&<div className="mz-mgrid"><i/><i/><i/></div>}</div>}
  {s==='grid'&&<div className="mz-mhero"><div className="l2"/><div className="mz-mgrid"><i/><i/><i/></div><div className="mz-mgrid"><i/><i/><i/></div></div>}
  {s==='pic'&&<div className="mz-mhero mz-split"><div className="mz-col"><div className="l1"/><div className="l2"/><div className="cta"/></div><div className="mz-pic"/></div>}
  {s==='lines'&&<div className="mz-mhero mz-center"><div className="l1"/><div className="l2"/></div>}
  {s==='form'&&<div className="mz-mhero"><div className="l2"/><div className="mz-field-line"/><div className="mz-field-line"/><div className="cta"/></div>}
 </div></div>;
}
