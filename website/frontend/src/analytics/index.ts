/**
 * The website's measurement (ADR-016).
 *
 * 1. First-party, cookieless: each page view and event is a tiny beacon to the website API
 *    (POST /analytics/event), which only adds one to a daily counter (day, page, event,
 *    language, the referring site's host). No cookie, no identifier, no IP or browser stored.
 *    The Mizan team reads the totals in the admin panel (Website).
 * 2. Google Analytics 4, only if VITE_GA4_ID is set and only after the visitor accepts it in the
 *    consent banner (consent.ts). The same events are sent there under GA4's names.
 */
import { gaEvent } from "./ga4";

export type SiteEvent =
  | "whatsapp_click"
  | "phone_click"
  | "contact_submit"
  | "demo_request"
  | "signup_start"
  | "signup_complete";

/** GA4's recommended event for each of ours (https://support.google.com/analytics/answer/9267735). */
const GA4_NAME: Record<SiteEvent, { name: string; params?: Record<string, string> }> = {
  whatsapp_click: { name: "contact", params: { method: "whatsapp" } },
  phone_click: { name: "contact", params: { method: "phone" } },
  contact_submit: { name: "generate_lead", params: { lead_source: "contact_form" } },
  demo_request: { name: "generate_lead", params: { lead_source: "demo_request" } },
  signup_start: { name: "sign_up_start" },
  signup_complete: { name: "sign_up", params: { method: "website" } },
};

const API = ((import.meta.env.VITE_API_URL as string | undefined) ?? "/api").replace(/\/+$/, "");

function send(body: Record<string, string>): void {
  if (typeof fetch === "undefined") return;
  try {
    // A "simple" request (text/plain, no-cors): no preflight, nothing to wait for. Not sendBeacon:
    // it always sends cookies, and this counter neither reads nor sets any (credentials: omit).
    // keepalive lets it finish when the visitor is leaving the page (signup, WhatsApp).
    void fetch(`${API}/analytics/event`, {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "text/plain" },
      mode: "no-cors",
      credentials: "omit",
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* measurement never breaks the page */
  }
}

const lang = () => (document.documentElement.lang === "en" ? "en" : "ar");

let lastPath = "";

/** A page view; the referrer's host only on the first page of a visit, and only if it's another site. */
export function trackPageView(path: string, title: string): void {
  if (path === lastPath) return;
  const first = lastPath === "";
  lastPath = path;
  let ref = "";
  if (first && document.referrer) {
    try {
      const host = new URL(document.referrer).hostname;
      if (host !== window.location.hostname) ref = host;
    } catch {
      /* no referrer */
    }
  }
  send({ kind: "pageview", name: "page_view", path, lang: lang(), ...(ref ? { ref } : {}) });
  gaEvent("page_view", { page_path: path, page_location: window.location.href, page_title: title, language: lang() });
}

export function track(event: SiteEvent, params: Record<string, string> = {}): void {
  send({ kind: "event", name: event, path: window.location.pathname, lang: lang() });
  const ga = GA4_NAME[event];
  gaEvent(ga.name, { ...ga.params, ...params });
}

/** WhatsApp and phone links anywhere on the site count as contacts, without wiring each link. */
export function trackContactClicks(): () => void {
  const onClick = (e: MouseEvent) => {
    const a = (e.target as Element | null)?.closest?.("a[href]");
    const href = a?.getAttribute("href") ?? "";
    if (href.startsWith("https://wa.me/")) track("whatsapp_click");
    else if (href.startsWith("tel:")) track("phone_click");
  };
  document.addEventListener("click", onClick, { capture: true });
  return () => document.removeEventListener("click", onClick, { capture: true });
}
