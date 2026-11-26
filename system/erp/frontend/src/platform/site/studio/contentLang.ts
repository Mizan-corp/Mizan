// Content editing language selection for the native tree editor.
// Keeps the editor's chosen content language across in-app page switches:
// switching pages must never silently drop the user's language, or text
// typed for one language lands in another language's fields. Page TITLES
// are not the gate: a page with an English-only title still holds Arabic
// content, so availability is judged by titles only when picking the
// default on the very first load. After that the selection always stays.
export type ContentLang = 'en' | 'ar';

export function pickContentLanguage(available: string[], previous: ContentLang, firstLoad: boolean): ContentLang {
  if (!firstLoad) return previous;
  if (available.includes(previous)) return previous;
  return available.includes('en') ? 'en' : 'ar';
}
