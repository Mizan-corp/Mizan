/**
 * Google Analytics 4, behind the visitor's consent (consent.ts). Nothing is loaded and no request
 * goes to Google unless VITE_GA4_ID is set and the visitor accepted.
 */
export const GA4_ID = ((import.meta.env.VITE_GA4_ID as string | undefined) ?? "").trim();

type Gtag = (...args: unknown[]) => void;
declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: Gtag;
  }
}

let loaded = false;

export function loadGa4(): void {
  if (loaded || !GA4_ID || typeof window === "undefined") return;
  loaded = true;
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag() {
    // gtag.js reads the arguments object itself.
    // eslint-disable-next-line prefer-rest-params
    window.dataLayer!.push(arguments);
  };
  window.gtag("consent", "default", { analytics_storage: "granted", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied" });
  window.gtag("js", new Date());
  // Page views are sent by the router (trackPageView), once per page.
  window.gtag("config", GA4_ID, { send_page_view: false });
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(GA4_ID)}`;
  document.head.appendChild(s);
}

/** The visitor withdrew consent: stop measuring and drop Google's cookies. */
export function stopGa4(): void {
  if (!loaded || !window.gtag) return;
  window.gtag("consent", "update", { analytics_storage: "denied" });
  for (const c of document.cookie.split(";")) {
    const name = c.split("=")[0].trim();
    if (name === "_ga" || name.startsWith("_ga_")) {
      for (const domain of ["", `; domain=.${window.location.hostname.replace(/^www\./, "")}`]) {
        document.cookie = `${name}=; Max-Age=0; path=/${domain}`;
      }
    }
  }
}

export function gaEvent(name: string, params: Record<string, string>): void {
  if (loaded && window.gtag) window.gtag("event", name, params);
}
