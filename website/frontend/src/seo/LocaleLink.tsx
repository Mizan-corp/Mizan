import { useLayoutEffect, type ReactNode } from "react";
import { Link as RouterLink, type LinkProps } from "react-router-dom";
import { applyHtmlDirection, LocaleScope, useI18nStore, useTranslation } from "@/i18n";
import { localizeHref, type Lang } from "./paths";

/**
 * The router's Link, kept in the page's language: on an English page "/pricing" leads to
 * "/en/pricing" (pages without an English version stay Arabic). Use it for every internal link
 * of the public pages.
 */
export function Link({ to, ...rest }: LinkProps) {
  const { locale } = useTranslation();
  return <RouterLink to={typeof to === "string" ? localizeHref(to, locale) : to} {...rest} />;
}

/** A path in the page's language, for navigate() and links built by hand. */
export function useLocalePath(): (path: string) => string {
  const { locale } = useTranslation();
  return (path) => localizeHref(path, locale);
}

/**
 * Fixes the language of the pages below it (from their address, not the saved choice), so the
 * pre-rendered HTML and the browser agree. Also keeps <html lang dir> right on client navigation.
 */
export function LangScope({ lang, children }: { lang: Lang; children: ReactNode }) {
  useLayoutEffect(() => {
    if (useI18nStore.getState().locale !== lang) {
      useI18nStore.setState({ locale: lang, dir: lang === "ar" ? "rtl" : "ltr" });
    }
    applyHtmlDirection(lang);
  }, [lang]);
  return <LocaleScope.Provider value={lang}>{children}</LocaleScope.Provider>;
}
