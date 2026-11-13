/**
 * Where the developer platform lives (ADR-007 D6): its own host, dev.allmizan.live, served by
 * this app. On that host its pages are at the root; elsewhere (development, previews) under /dev.
 */
export const DEV_HOST = typeof window !== "undefined" && window.location.hostname.startsWith("dev.");
export const DEV_BASE = DEV_HOST ? "" : "/dev";

/** A developer-platform path: devPath("/docs") is "/docs" on dev.allmizan.live, "/dev/docs" elsewhere. */
export function devPath(path = "/"): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return DEV_BASE ? (p === "/" ? DEV_BASE : `${DEV_BASE}${p}`) : p;
}

/** The developer platform's address from elsewhere on the website (dev.allmizan.live in production). */
const DEV_URL = ((import.meta.env.VITE_DEV_PORTAL_URL as string | undefined) ?? "").replace(/\/+$/, "");
export function devUrl(path = "/"): string {
  if (DEV_HOST || !DEV_URL) return devPath(path);
  return `${DEV_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
