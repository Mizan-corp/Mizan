import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { DEV_HOST } from "@app/features/developers/paths";
import { trackContactClicks, trackPageView } from "@app/analytics";
import { startAnalyticsConsent } from "@app/analytics/consent";
import { ConsentBanner } from "@app/analytics/ConsentBanner";
import { langOf } from "./paths";

// Toasts only follow an action: their code loads after the page is up.
const Toaster = lazy(() => import("@/components/kit/sonner").then((m) => ({ default: m.Toaster })));

/**
 * What the browser does around the pages (ADR-016): moves the head along when the visitor
 * changes page (the first page's head came pre-rendered), counts page views, and shows the
 * analytics consent banner. Renders nothing on the server.
 */
export function SiteEffects() {
  const location = useLocation();
  const first = useRef(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    startAnalyticsConsent();
    return trackContactClicks();
  }, []);

  useEffect(() => {
    const path = location.pathname;
    if (first.current) {
      first.current = false;
      trackPageView(path, document.title);
      return;
    }
    if (DEV_HOST || path.startsWith("/dev")) {
      trackPageView(path, document.title);
      return;
    }
    let cancelled = false;
    // The head data is loaded only when needed: the first page doesn't need it.
    void Promise.all([import("./pages"), import("./head")]).then(([pages, head]) => {
      if (cancelled) return;
      const page = pages.seoFor(path, langOf(path));
      document.title = page.title;
      document.head.querySelectorAll("[data-seo]").forEach((el) => el.remove());
      for (const t of head.headTags(page)) {
        const el = document.createElement(t.tag);
        for (const [k, v] of Object.entries(t.attrs)) el.setAttribute(k, v);
        el.setAttribute("data-seo", "");
        if (t.text) el.textContent = t.text;
        document.head.appendChild(el);
      }
      trackPageView(path, page.title);
    });
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  if (!mounted) return null;
  return (
    <>
      <ConsentBanner />
      <Suspense fallback={null}>
        <Toaster position="top-center" dir="rtl" />
      </Suspense>
    </>
  );
}
