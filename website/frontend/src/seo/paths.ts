/**
 * The website's addresses and their languages (ADR-016). Arabic pages live at "/…" (unchanged),
 * English ones under "/en/…". Only the pages listed in EN_PAGES have an English version; a link
 * to any other page from an English page stays on the Arabic page.
 */
export type Lang = "ar" | "en";

export const LANGS: Lang[] = ["ar", "en"];

/** Pages with an English version (base paths, without "/en"). */
export const EN_PAGES: ReadonlySet<string> = new Set([
  "/",
  "/product",
  "/features",
  "/features/inventory",
  "/industries",
  "/pricing",
  "/about",
  "/contact",
  "/demo",
  "/terms",
  "/privacy",
  "/refund-policy",
]);

/** Application pages that follow the visitor's language but are never indexed. */
export const EN_APP_PAGES: ReadonlySet<string> = new Set(["/signup"]);

export function langOf(pathname: string): Lang {
  return pathname === "/en" || pathname.startsWith("/en/") ? "en" : "ar";
}

/** "/en/pricing" → "/pricing", "/en" → "/". */
export function basePath(pathname: string): string {
  if (pathname === "/en") return "/";
  return pathname.startsWith("/en/") ? pathname.slice(3) : pathname;
}

/** ("/pricing", "en") → "/en/pricing", ("/", "en") → "/en". */
export function withLang(path: string, lang: Lang): string {
  if (lang === "ar") return path;
  return path === "/" ? "/en" : `/en${path}`;
}

export function hasVersion(path: string, lang: Lang): boolean {
  return lang === "ar" || EN_PAGES.has(path) || EN_APP_PAGES.has(path);
}

/**
 * An internal link for a page in `lang`: "/pricing" from an English page is "/en/pricing";
 * "/blog" (Arabic only) stays "/blog". Query strings and fragments are kept.
 */
export function localizeHref(to: string, lang: Lang): string {
  if (lang === "ar" || !to.startsWith("/") || to.startsWith("//")) return to;
  const cut = to.search(/[?#]/);
  const path = cut === -1 ? to : to.slice(0, cut);
  const rest = cut === -1 ? "" : to.slice(cut);
  if (langOf(path) === "en") return to;
  return hasVersion(path, "en") ? `${withLang(path, "en")}${rest}` : to;
}

/** The same page in the other language, or that language's home when there is none. */
export function alternatePath(pathname: string, lang: Lang): string {
  const base = basePath(pathname);
  return hasVersion(base, lang) ? withLang(base, lang) : withLang("/", lang);
}
