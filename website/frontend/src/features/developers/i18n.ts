/**
 * The developer platform's language: English by default (developers anywhere), Arabic on request.
 * Kept apart from the website's own choice (mizan.locale, Arabic by default), so switching here
 * doesn't change the rest of the website.
 */
import { applyHtmlDirection, useI18nStore, type Locale } from "@/i18n";

const KEY = "mizan.dev_locale";

export function devLocale(): Locale {
  return localStorage.getItem(KEY) === "ar" ? "ar" : "en";
}

/** Show the developer platform in `locale` (and remember it for the platform only). */
export function setDevLocale(locale: Locale): void {
  localStorage.setItem(KEY, locale);
  useI18nStore.setState({ locale, dir: locale === "ar" ? "rtl" : "ltr" });
  applyHtmlDirection(locale);
}

/** Leaving the platform: the website's own language again. */
export function restoreSiteLocale(): void {
  const saved = localStorage.getItem("mizan.locale");
  const locale: Locale = saved === "en" ? "en" : "ar";
  useI18nStore.setState({ locale, dir: locale === "ar" ? "rtl" : "ltr" });
  applyHtmlDirection(locale);
}

/** t("English", "العربية") for the current language. */
export function useDevI18n() {
  const locale = useI18nStore((s) => s.locale);
  const isAr = locale === "ar";
  return {
    locale,
    isAr,
    dir: (isAr ? "rtl" : "ltr") as "rtl" | "ltr",
    t: (en: string, ar: string) => (isAr ? ar : en),
    toggle: () => setDevLocale(isAr ? "en" : "ar"),
  };
}

/** For code outside React (the API client). */
export const devIsArabic = () => useI18nStore.getState().locale === "ar";
