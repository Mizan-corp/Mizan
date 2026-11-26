import type {PageSummary} from './sitePages';
/** Stage a same-site address only. This does not publish or promise a public route. */
export function selectedPageAddress(pages:PageSummary[],id:string):string{
 const matches=pages.filter(p=>p.id===id);
 if(matches.length!==1)throw Error('Refresh pages and choose one current page.');
 const page=matches[0];
 if(page.status==='archived'||!['draft','published'].includes(page.status)||!page.has_draft&&!page.published||!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(page.slug)||page.slug.length>80)throw Error('This page is unavailable as a navigation destination.');
 return '/'+page.slug;
}
