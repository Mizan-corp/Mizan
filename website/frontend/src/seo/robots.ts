import { SITE_URL } from "./pages";

/**
 * robots.txt for allmizan.live and for dev.allmizan.live (nginx serves robots-dev.txt there).
 * Application pages on allmizan.live (signup, the owner panel…) stay crawlable on purpose: they
 * answer with "X-Robots-Tag: noindex" (deploy/server/nginx.conf), which a crawler only sees if
 * it may fetch them. The other hosts (the ERP, the APIs) disallow everything.
 */
export function robotsTxt(host: "site" | "dev"): string {
  if (host === "dev") {
    // The developer platform: its public pages and docs are open; the portal needs a sign-in.
    return ["User-agent: *", "Disallow: /portal", ""].join("\n");
  }
  return ["User-agent: *", "Disallow: /admin/", "Disallow: /dev/", "", `Sitemap: ${SITE_URL}/sitemap.xml`, ""].join("\n");
}
