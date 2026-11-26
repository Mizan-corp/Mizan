import { createContext, useContext } from "react";
import { create } from "zustand";
import { translations } from "./translations";

export type Locale = "ar" | "en";
export type Direction = "rtl" | "ltr";

interface I18nState {
  locale: Locale;
  dir: Direction;
  setLocale: (locale: Locale) => void;
  toggleLocale: () => void;
  t: (path: string, fallback?: string) => string;
}

const STORAGE_KEY = "mizan.locale";
const LEGACY_STORAGE_KEY = "vendora.locale";

/**
 * A page whose address decides its language (the website's pre-rendered pages: "/…" Arabic,
 * "/en/…" English) says so with <html data-locale="url">; its lang wins over the saved choice.
 */
function urlLocale(): Locale | null {
  if (typeof document === "undefined" || document.documentElement.dataset.locale !== "url") return null;
  return document.documentElement.lang === "en" ? "en" : "ar";
}

function getInitialLocale(): Locale {
  const fixed = urlLocale();
  if (fixed) return fixed;
  if (typeof localStorage === "undefined") return "ar";
  const saved = localStorage.getItem(STORAGE_KEY) ?? localStorage.getItem(LEGACY_STORAGE_KEY);
  if (saved === "ar" || saved === "en") return saved;
  return "ar";
}

export function applyHtmlDirection(locale: Locale) {
  const dir = locale === "ar" ? "rtl" : "ltr";
  document.documentElement.lang = locale;
  document.documentElement.dir = dir;
  if (dir === "ltr") {
    document.body.classList.add("ltr");
    document.body.classList.remove("rtl");
  } else {
    document.body.classList.add("rtl");
    document.body.classList.remove("ltr");
  }
}

// Initial application on file load
if (typeof window !== "undefined" && !urlLocale()) {
  const initial = getInitialLocale();
  applyHtmlDirection(initial);
}

export const useI18nStore = create<I18nState>((set, get) => ({
  locale: getInitialLocale(),
  dir: getInitialLocale() === "ar" ? "rtl" : "ltr",

  setLocale: (locale: Locale) => {
    localStorage.setItem(STORAGE_KEY, locale);
    applyHtmlDirection(locale);
    set({ locale, dir: locale === "ar" ? "rtl" : "ltr" });
  },

  toggleLocale: () => {
    const nextLocale: Locale = get().locale === "ar" ? "en" : "ar";
    get().setLocale(nextLocale);
  },

  t: (path: string, fallback?: string): string => translate(get().locale, path, fallback),
}));

function translate(currentLocale: Locale, path: string, fallback?: string): string {
  const dict = translations[currentLocale];
  const parts = path.split(".");

  let cursor: any = dict;
  for (const part of parts) {
    if (cursor && typeof cursor === "object" && part in cursor) {
      cursor = cursor[part];
    } else {
      return fallback || path;
    }
  }

  return typeof cursor === "string" ? cursor : fallback || path;
}

/**
 * A part of the tree whose language is fixed, whatever the saved choice: the website gives each
 * page its language from the address (ADR-016), so the server and the browser render the same.
 */
export const LocaleScope = createContext<Locale | null>(null);

export function useTranslation() {
  const { locale, dir, setLocale, toggleLocale, t } = useI18nStore();
  const scoped = useContext(LocaleScope);
  if (scoped && scoped !== locale) {
    return {
      locale: scoped,
      dir: (scoped === "ar" ? "rtl" : "ltr") as Direction,
      setLocale,
      toggleLocale,
      t: (path: string, fallback?: string) => translate(scoped, path, fallback),
    };
  }
  return { locale, dir, setLocale, toggleLocale, t };
}
