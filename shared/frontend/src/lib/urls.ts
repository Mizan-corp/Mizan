/**
 * Where each Mizan app lives. The website, the system (ERP), the owner panel
 * and the admin panel are deployed separately; links between them must be absolute.
 */
export type AppKind = "website" | "system" | "owner" | "admin";

export const APP_KIND = (import.meta.env.VITE_APP_KIND as AppKind | undefined) ?? "system";

const trim = (u: string) => u.replace(/\/+$/, "");

export const APP_URLS: Record<AppKind, string> = {
  website: trim((import.meta.env.VITE_WEBSITE_URL as string | undefined) ?? "https://mizan-co.vercel.app"),
  system: trim((import.meta.env.VITE_SYSTEM_URL as string | undefined) ?? "https://mizan-co-app.vercel.app"),
  owner: trim((import.meta.env.VITE_OWNER_URL as string | undefined) ?? "https://mizan-co-owner.vercel.app"),
  admin: trim((import.meta.env.VITE_ADMIN_URL as string | undefined) ?? "https://mizan-co-admin.vercel.app"),
};

/** The owner API, for apps other than the owner panel (the website checks the owner's session). */
export const OWNER_API_URL = trim(
  (import.meta.env.VITE_OWNER_API_URL as string | undefined) ?? "https://mizan-co-owner-api.vercel.app/api",
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

/** Absolute URL to a path in another app (or this one). */
export function appUrl(app: AppKind, path = "/"): string {
  return `${APP_URLS[app]}${path.startsWith("/") ? path : `/${path}`}`;
}
