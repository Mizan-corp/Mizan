import { useEffect, useRef, useState } from 'react';
import type { PageNode } from './pagetree';
import { nativeContentFields, safeNativeUrl, type NativeIconItem } from './nativeTree';
import { sanitizeHtml } from './treerender';
import { iconNames } from './nativeIcons';
import {t} from './uiStrings';

export default function NativeContentControls({node,lang,onEdit,onEditItems}:{node:PageNode;lang:'en'|'ar';onEdit:(field:string,value:string)=>void;onEditItems?:(items:NativeIconItem[])=>void}){
  const rich=useRef<HTMLDivElement>(null);
  const headingEl=useRef<HTMLTextAreaElement>(null);
  const [urlError,setUrlError]=useState('');
  const ar=true; // Arabic-first UI chrome, content lang suffix kept
  const content=node.content[lang]??{};
  const html=String(content.html??'');
  useEffect(()=>{if(rich.current && sanitizeHtml(rich.current.innerHTML)!==sanitizeHtml(html))rich.current.innerHTML=sanitizeHtml(html)},[node.id,lang,html]);
  const commitRich=()=>{if(!rich.current)return;const next=sanitizeHtml(rich.current.innerHTML);if(next!==sanitizeHtml(html))onEdit('html',next);};
  const toggleAccent=()=>{const el=headingEl.current;if(!el)return;const a=el.selectionStart??0,b=el.selectionEnd??0,value=String(content.text??'');if(a===b)return;const sel=value.slice(a,b);let next,na;
    if(value.slice(a-6,a)==='<mark>'&&value.slice(b,b+7)==='</mark>'){next=value.slice(0,a-6)+sel+value.slice(b+7);na=a-6;}
    else{next=value.slice(0,a)+'<mark>'+sel+'</mark>'+value.slice(b);na=a+6;}
    onEdit('text',next);requestAnimationFrame(()=>{el.focus();el.setSelectionRange(na,na+sel.length);});};
  return <div className="native-content-controls">
    {node.type==='text'&&<div className="native-rich"><label>{ar?t('النص'):'Text'} · {lang}</label><div className="native-rich-toolbar">{[[ar?t('عريض'):'Bold','bold'],[ar?t('مائل'):'Italic','italic'],[ar?t('نقاط'):'Bullets','insertUnorderedList']] .map(([label,command])=><button type="button" key={command} onMouseDown={e=>e.preventDefault()} onClick={()=>{rich.current?.focus();document.execCommand(command);commitRich()}}>{label}</button>)}</div><div ref={rich} contentEditable role="textbox" aria-label="Native rich text" aria-multiline="true" suppressContentEditableWarning onInput={commitRich}/><p className="hint">{ar?t('عدّل النص مباشرة. التنسيق المحفوظ بيفضل زي ما هو لحد ما تعدّل الحقل ده.'):'Edit text directly. Existing stored markup stays unchanged until you edit this field.'}</p></div>}
    {node.type==='heading'&&<div className="native-rich"><label>{t('نص العنوان')} · {lang}</label><div className="native-rich-toolbar"><button type="button" onMouseDown={e=>e.preventDefault()} onClick={toggleAccent}>{t('تمييز')}</button></div><textarea ref={headingEl} aria-label="Native text" maxLength={nativeContentFields('heading').text??200} value={String(content.text??'')} onChange={e=>onEdit('text',e.target.value)}/><p className="hint">{t('حدّد كلمة ودوس تمييز عشان تظهر بلون الموقع الأساسي. التمييز الوحيد المدعوم في العناوين.')}</p></div>}
    {Object.entries(nativeContentFields(node.type)).filter(([field])=>field!=='html'&&!(node.type==='heading'&&field==='text')).map(([field,max])=>{
      const label=!ar?(field==='src'?'Image address':field==='alt'?'Image description':field==='href'?'Link destination':field==='label'?'Button text':'Heading text'):(field==='src'?t('عنوان الصورة'):field==='alt'?t('وصف الصورة'):field==='href'?t('وجهة الرابط'):field==='label'?t('نص الزر'):t('نص العنوان'));
      if(field==='src'||field==='href')return <label key={field}>{label} · {lang}<input key={`${node.id}-${lang}-${field}-${String(content[field])}`} aria-label={`Native ${field}`} defaultValue={String(content[field]??'')} maxLength={max} placeholder={field==='src'?'https://... or /media/...':'/page or https://...'} onBlur={e=>{if(!safeNativeUrl(e.target.value,field==='src')){setUrlError(ar?t('العنوان مرفوض. الوجهة المحفوظة ما اتغيرتش.'):'Address refused. The stored destination is unchanged.');return;}setUrlError('');onEdit(field,e.target.value)}}/>{urlError&&<span className="link-error" role="status">{urlError}</span>}<small>{ar?t('بيتحفظ لما تسيب الحقل. مفيش رفع ملفات ولا شراء.'):'Applied when you leave the field. No file upload or purchase.'}</small></label>;
      return <label key={field}>{label} · {lang}<textarea aria-label={`Native ${field}`} maxLength={max} value={String(content[field]??'')} onChange={e=>onEdit(field,e.target.value)}/></label>;
    })}
    {node.type==='image'&&typeof content.src==='string'&&content.src&&safeNativeUrl(content.src,true)&&<img className="native-media-thumbnail" src={content.src} alt={String(content.alt??(ar?t('معاينة الصورة'):'Image preview'))}/>}
    {node.type==='icon_list'&&onEditItems&&(()=>{
      const items:NativeIconItem[]=(Array.isArray(content.items)?content.items:[]).filter((e):e is NativeIconItem=>!!e&&typeof e==='object'&&typeof (e as NativeIconItem).icon==='string');
      const update=(i:number,next:NativeIconItem)=>onEditItems(items.map((e,j)=>j===i?next:e));
      return <div className="native-rich"><label>{t('عناصر الأيقونات')} · {lang}</label>
        {items.map((item,i)=><div className="native-icon-item" key={i}>
          <select aria-label={`Icon ${i+1}`} value={item.icon} onChange={e=>update(i,{...item,icon:e.target.value})}>
            {Array.from(new Set([item.icon,...iconNames()])).filter(Boolean).map(name=><option key={name} value={name}>{name}</option>)}
          </select>
          <input aria-label={`Item text ${i+1}`} maxLength={120} value={item.text} onChange={e=>update(i,{...item,text:e.target.value})}/>
          <button type="button" aria-label={`Remove item ${i+1}`} onClick={()=>onEditItems(items.filter((_,j)=>j!==i))}>{t('احذف')}</button>
        </div>)}
        <button type="button" disabled={items.length>=24} onClick={()=>onEditItems([...items,{icon:'Check',text:''}])}>{t('ضيف عنصر')}</button>
        <p className="hint">{t('اختار أيقونة من المجموعة الجاهزة واكتب نصًا قصيرًا. الحفظ بيتم مع باقي الصفحة.')}</p>
      </div>;
    })()}
  </div>;
}
