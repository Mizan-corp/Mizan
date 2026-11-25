// Content editing language selection for the native tree editor.
// Keeps the editor's chosen content language across in-app page switches:
// switching pages must never silently drop the user's language, or text
// typed for one language lands in another language's fields.
export type ContentLang = 'en' | 'ar';

export function pickContentLanguage(available: string[], previous: ContentLang): ContentLang {
  if (available.includes(previous)) return previous;
  return available.includes('en') ? 'en' : 'ar';
}
