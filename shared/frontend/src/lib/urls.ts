/**
 * Where each Mizan app lives. The website, the system (ERP) and the admin panel
 * are deployed separately; links between them must be absolute.
 */
export type AppKind = "website" | "system" | "admin";

export const APP_KIND = (import.meta.env.VITE_APP_KIND as AppKind | undefined) ?? "system";

const trim = (u: string) => u.replace(/\/+$/, "");

export const APP_URLS: Record<AppKind, string> = {
  website: trim((import.meta.env.VITE_WEBSITE_URL as string | undefined) ?? "https://mizan-co.vercel.app"),
  system: trim((import.meta.env.VITE_SYSTEM_URL as string | undefined) ?? "https://mizan-co-app.vercel.app"),
  admin: trim((import.meta.env.VITE_ADMIN_URL as string | undefined) ?? "https://mizan-co-admin.vercel.app"),
};

/** Absolute URL to a path in another app (or this one). */
export function appUrl(app: AppKind, path = "/"): string {
  return `${APP_URLS[app]}${path.startsWith("/") ? path : `/${path}`}`;
}
