import {nativeTreeKey,safeNativeUrl} from './nativeTree';
import type {SiteSettingsValue} from './sitePages';
export type ChromePart='header'|'footer';
export type ChromeVariant='header_inline'|'header_centered'|'footer_split'|'footer_stacked';
export const chromeCatalog:{id:ChromeVariant;part:ChromePart;name:string}[]=[{id:'header_inline',part:'header',name:'Inline navigation'},{id:'header_centered',part:'header',name:'Centered navigation'},{id:'footer_split',part:'footer',name:'Split footer'},{id:'footer_stacked',part:'footer',name:'Stacked footer'}];
export function chromePreset(value:SiteSettingsValue,variant:ChromeVariant):SiteSettingsValue{
 const next=structuredClone(value);
 if(variant.startsWith('header_'))next.header={...next.header,brand:next.header?.brand??'Your brand',links:next.header?.links??[{label:'About',href:'/about'},{label:'Contact',href:'/contact'}],actions:next.header?.actions??[],layout:variant==='header_centered'?'centered':'inline'};
 else next.footer={...next.footer,lines:next.footer?.lines??['Your brand. Your story.'],links:next.footer?.links??[{label:'Contact',href:'/contact'}],layout:variant==='footer_stacked'?'stacked':'split'};
 return next;
}
/** Refuse a lossy shared save. Unknown metadata stays in memory but is not silently dropped by API normalization. */
export function chromeProblems(value:SiteSettingsValue):string[]{
 const errors:string[]=[];
 const contrast=(a:string,b:string)=>{const luminance=(hex:string)=>{const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*c[0]+.7152*c[1]+.0722*c[2]};const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
 const light=value.colors?.light;
 if(light)for(const [fg,bg]of [['foreground','background'],['foreground','card'],['primary-foreground','primary'],['dark-foreground','dark']]){const a=light[fg],b=light[bg];if(a&&b&&/^#[0-9a-fA-F]{6}$/.test(a)&&/^#[0-9a-fA-F]{6}$/.test(b)&&contrast(a,b)<4.5)errors.push('Increase contrast between '+fg+' and '+bg+' to at least 4.5:1.');}

 const normalized=structuredClone(value);
 for(const part of ['header','footer']as const){const s=value[part];if(s)normalized[part]=(part==='header'?{brand:(value.header?.brand??'').trim(),links:value.header?.links??[],actions:value.header?.actions??[],...(value.header?.layout?{layout:value.header.layout}:{}),...(value.header?.surface?{surface:value.header.surface}:{}),...(value.header?.logo?{logo:value.header.logo}:{}),...(value.header?.search_enabled!==undefined?{search_enabled:value.header.search_enabled}:{}),...(value.header?.search_target?{search_target:value.header.search_target}:{}),...(value.header?.search_placeholder?.trim()?{search_placeholder:value.header.search_placeholder.trim()}:{}),...(value.header?.search_style?{search_style:value.header.search_style}:{}),...(value.header?.bar_style?{bar_style:value.header.bar_style}:{}),...(value.header?.density?{density:value.header.density}:{}),...(value.header?.icons?{icons:value.header.icons}:{}),...(value.header?.bar_links?{bar_links:value.header.bar_links}:{}),...(value.header?.bar_cta_label?.trim()?{bar_cta_label:value.header.bar_cta_label.trim()}:{}),...(value.header?.bar_cta_href?{bar_cta_href:value.header.bar_cta_href}:{})}:{lines:value.footer?.lines??[],links:value.footer?.links??[],...(value.footer?.layout?{layout:value.footer.layout}:{}),...(value.footer?.groups?.length?{groups:value.footer.groups}:{})})as never;}
 if(nativeTreeKey(normalized)!==nativeTreeKey(value))errors.push('Shared settings are not in the supported lossless format.');

 if(value.colors&&(Object.keys(value.colors).some(k=>k!=='light')||!value.colors.light||Object.entries(value.colors.light).some(([k,v])=>!['background','foreground','card','primary','primary-foreground','dark','dark-foreground','dark-raised'].includes(k)||!/^#[0-9a-fA-F]{6}$/.test(v))))errors.push('Shared colors contain unsupported values.');
 if(value.typography&&(Object.keys(value.typography).some(k=>k!=='family')||!['sans-serif','serif','monospace'].includes(value.typography.family??'')))errors.push('Shared typography is not supported.');
 if(value.shape&&(Object.keys(value.shape).some(k=>k!=='radius')||!Number.isInteger(value.shape.radius)||value.shape.radius!<0||value.shape.radius!>64))errors.push('Shared shape is not supported.');

 if(Object.keys(value).some(k=>!['header','footer','colors','typography','shape','follow_workspace'].includes(k)))errors.push('Shared settings contain fields this editor cannot preserve.');
 if(value.follow_workspace!==undefined&&typeof value.follow_workspace!=='boolean')errors.push('Shared follow_workspace flag is not a boolean.');
 for(const part of ['header','footer'] as const){const section=value[part];if(!section)continue;
  if(Object.keys(section).some(k=>!(part==='header'?['brand','logo','links','actions','layout','surface','search_enabled','search_target','search_placeholder','search_style','bar_style','density','icons','bar_links','bar_cta_label','bar_cta_href']:['lines','links','groups','layout']).includes(k)))errors.push('Shared '+part+' has unsupported fields.');
  for(const field of part==='header'?['links','actions','bar_links']:['links']){const links=(section as Record<string,unknown>)[field];if(links!==undefined&&(!Array.isArray(links)||links.length>(field==='actions'?4:field==='bar_links'?12:8)||links.some(l=>!l||Object.keys(l).some(k=>!['label','href'].includes(k))||typeof l.label!=='string'||l.label!==l.label.trim()||!l.label.trim()||l.label.length>40||typeof l.href!=='string'||l.href.length>200||!safeNativeUrl(l.href)||!(/^(\/|#|https:\/\/)/.test(l.href)))))errors.push('Use a label and safe /path, #anchor or https:// link for every '+field+'.');}
 }
 if(value.header?.brand!==undefined&&(value.header.brand.length>80||value.header.brand!==value.header.brand.trim()))errors.push('Brand must have no outer spaces and at most 80 characters.');
 if(value.header?.logo!==undefined&&(typeof value.header.logo!=='string'||!value.header.logo||value.header.logo!==value.header.logo.trim()||value.header.logo.length>300||!/^(\/|https:\/\/)/.test(value.header.logo)||!safeNativeUrl(value.header.logo,true)))errors.push('استخدم عنوان /مسار أو https:// سليم للوجو، من غير مسافات زيادة.');
 const footerGroups=value.footer?.groups;
 if(footerGroups!==undefined&&(!Array.isArray(footerGroups)||footerGroups.length>4||footerGroups.some(g=>!g||Object.keys(g).some(k=>!['title','links'].includes(k))||typeof g.title!=='string'||g.title!==g.title.trim()||!g.title.trim()||g.title.length>40||!Array.isArray(g.links)||g.links.length>6||g.links.some(l=>!l||Object.keys(l).some(k=>!['label','href'].includes(k))||typeof l.label!=='string'||l.label!==l.label.trim()||!l.label.trim()||l.label.length>40||typeof l.href!=='string'||l.href.length>200||!safeNativeUrl(l.href)||!/^(\/|#|https:\/\/)/.test(l.href)))))errors.push('كل مجموعة لينكات فوتر تحتاج عنوان قصير وحتى ٦ لينكات سليمة.');
 if(value.header?.search_enabled!==undefined&&typeof value.header.search_enabled!=='boolean')errors.push('Header search flag is not a boolean.');
 if(value.header?.search_target!==undefined&&(typeof value.header.search_target!=='string'||value.header.search_target.length>200||!/^\//.test(value.header.search_target)||!safeNativeUrl(value.header.search_target)))errors.push('استخدم مسار /داخلي سليم لصفحة نتائج البحث.');
 if(value.header?.search_placeholder!==undefined&&(typeof value.header.search_placeholder!=='string'||value.header.search_placeholder!==value.header.search_placeholder.trim()||value.header.search_placeholder.length>80))errors.push('نص خانة البحث لازم يكون من غير مسافات زيادة وبحد أقصى ٨٠ حرف.');
  for(const[f,opts]of[['search_style',['filled','outline']],['bar_style',['pills','plain']],['density',['comfortable','compact']]]as const){const v=(value.header as Record<string,unknown>|undefined)?.[f];if(v!==undefined&&!(opts as readonly string[]).includes(v as string))errors.push('قيمة '+f+' في الترويسة غير مدعومة.')}
 const headerIcons=value.header?.icons;
 if(headerIcons!==undefined&&(!Array.isArray(headerIcons)||headerIcons.length>6||headerIcons.some(ic=>!ic||Object.keys(ic).some(k=>!['icon','label','href'].includes(k))||!['whatsapp','cart','heart','user','phone','globe'].includes(ic.icon)||typeof ic.label!=='string'||ic.label!==ic.label.trim()||!ic.label.trim()||ic.label.length>40||typeof ic.href!=='string'||ic.href.length>200||!safeNativeUrl(ic.href)||!/^(\/|#|https:\/\/)/.test(ic.href))))errors.push('كل أيقونة ترويسة تحتاج نوع معروف وتسمية قصيرة ورابط سليم.');
 if(value.header?.bar_cta_label!==undefined&&(typeof value.header.bar_cta_label!=='string'||value.header.bar_cta_label!==value.header.bar_cta_label.trim()||value.header.bar_cta_label.length>40))errors.push('تسمية زر الشريط من غير مسافات زيادة وبحد أقصى ٤٠ حرف.');
 if(value.header?.bar_cta_href!==undefined&&(typeof value.header.bar_cta_href!=='string'||value.header.bar_cta_href.length>200||!safeNativeUrl(value.header.bar_cta_href)||!/^(\/|#|https:\/\/)/.test(value.header.bar_cta_href)))errors.push('رابط زر الشريط لازم يكون /مسار أو #عنصر أو https:// سليم.');
 if(value.header?.layout&&!['inline','centered'].includes(value.header.layout))errors.push('Unsupported header layout.');
 if(value.header?.surface&&!['default','dark'].includes(value.header.surface))errors.push('Unsupported header surface.');
 if(value.footer?.layout&&!['split','stacked'].includes(value.footer.layout))errors.push('Unsupported footer layout.');
 if((value.footer?.lines?.length??0)>4)errors.push('Use at most four footer lines.');
 if(value.footer?.lines?.some(l=>!l.trim()||l.length>120||l!==l.trim()))errors.push('Footer lines must be 1-120 characters without outer spaces.');
 return errors;
   }
