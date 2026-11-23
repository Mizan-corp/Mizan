/**
 * Where each Mizan app lives. The website, the system (ERP), the owner panel
 * and the admin panel are deployed separately; links between them must be absolute.
 */
export type AppKind = "website" | "system" | "owner" | "admin";

export const APP_KIND = (import.meta.env.VITE_APP_KIND as AppKind | undefined) ?? "system";

const trim = (u: string) => u.replace(/\/+$/, "");

export const APP_URLS: Record<AppKind, string> = {
  website: trim((import.meta.env.VITE_WEBSITE_URL as string | undefined) ?? "https://allmizan.live"),
  system: trim((import.meta.env.VITE_SYSTEM_URL as string | undefined) ?? "https://app.allmizan.live"),
  owner: trim((import.meta.env.VITE_OWNER_URL as string | undefined) ?? "https://allmizan.live/owner"),
  admin: trim((import.meta.env.VITE_ADMIN_URL as string | undefined) ?? "https://allmizan.live/admin"),
};

/** The owner API, for apps other than the owner panel (the website checks the owner's session). */
export const OWNER_API_URL = trim(
  (import.meta.env.VITE_OWNER_API_URL as string | undefined) ?? "https://owner-api.allmizan.live/api",
);

/**
 * Workspaces on their own subdomain (ADR-008): `<slug>.<VITE_WORKSPACE_DOMAIN>`. Without it
 * (older deployments, development) a workspace lives at `<system app>/c/<slug>`.
 */
export const WORKSPACE_DOMAIN = ((import.meta.env.VITE_WORKSPACE_DOMAIN as string | undefined) ?? "").trim().toLowerCase();

/** Absolute URL to a page of a workspace ("/" is its home, "/login" its sign-in). */
export function workspaceUrl(slug: string, path = "/"): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (WORKSPACE_DOMAIN) return `https://${slug}.${WORKSPACE_DOMAIN}${p}`;
  return appUrl("system", `/c/${slug}${p === "/" ? "" : p}`);
}

/**
 * The workspace ERP's path prefix on its host (ADR-015 S1): the storefront takes the
 * workspace host's root and the ERP moves under /admin. Empty until that move ships; set
 * VITE_ERP_BASE=/admin when it does. Every ERP-bound link goes through erpUrl so the
 * prefix lives in exactly one place (and S6 custom domains touch one function).
 */
const ERP_BASE = ((import.meta.env.VITE_ERP_BASE as string | undefined) ?? "").replace(/\/+$/, "");

/**
 * Absolute URL to a page of a workspace's ERP (today the workspace host itself; after S1,
 * <host>/<ERP_BASE>/...). Without a slug (older deployments, development) the ERP is the
 * system app. Links to a workspace's public pages (its site) keep using workspaceUrl.
 */
export function erpUrl(slug: string | null | undefined, path = "/"): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  const full = p === "/" ? ERP_BASE || "/" : `${ERP_BASE}${p}`;
  if (slug) return workspaceUrl(slug, full);
  return appUrl("system", full);
}

/** Absolute URL to a path in another app (or this one). */
export function appUrl(app: AppKind, path = "/"): string {
  return `${APP_URLS[app]}${path.startsWith("/") ? path : `/${path}`}`;
}

/** A `next`/return path that stays on this site: "/…" only. Rejects "//host", "/\host" (browsers
 * read it as "//host"), absolute URLs, and anything that would resolve to another host. */
export function safeInternalPath(raw: string | null | undefined, fallback = "/"): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return fallback;
  if (/[\u0000-\u001f\u007f]/.test(raw)) return fallback;
  try {
    const url = new URL(raw, "http://mizan.invalid");
    if (url.host !== "mizan.invalid") return fallback;
    return url.pathname + url.search + url.hash;
  } catch {
    return fallback;
  }
}

