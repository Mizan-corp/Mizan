# ADR-008: One domain, with workspaces on subdomains

## Status
Accepted (2026-11-12). Issue #116. Extends ADR-003 (separate apps) and ADR-004 (owner accounts).

## Context
The four products (website, ERP, owner panel, admin panel) and their four APIs ran on eight
`*.vercel.app` addresses. The owner bought **allmizan.live** and asked for one domain for
everything, with subdomains only for each workspace and, later, the developer portal.

## Decision

| Address | Serves | Vercel project |
|---|---|---|
| `allmizan.live/` (`www.` redirects) | Website: marketing, signup, help | `mizan-website` |
| `allmizan.live/login` | Owners' sign-in (forwards to `/owner/login`) | owner panel |
| `allmizan.live/owner/…` | Owner panel | `mizan-owner`, built with base `/owner/` |
| `allmizan.live/admin/…` | Admin panel | `mizan-admin`, built with base `/admin/` |
| `api.`, `owner-api.`, `web-api.`, `admin-api.allmizan.live` | The system, owner, website and admin APIs (called by the apps; never visited) | the four API projects |
| `<workspace>.allmizan.live/…` | That workspace's ERP | `mizan-system` (wildcard) |
| `dev.allmizan.live` | The developer platform: home, portal, developer docs, the SDK wheel (ADR-007, attached 2026-11-13) | `mizan-website` (the app shows the developer platform on `dev.*` hosts) |

- **The apex project proxies the panels.** `mizan-website` holds `allmizan.live`; its
  `vercel.json` rewrites `/owner` and `/admin` to those projects (static files). Each app still
  deploys on its own (ADR-003); visitors only see one domain.
- **APIs keep their own (technical) addresses.** Forwarding a request from one Vercel project
  to another replaces the visitor's IP with Vercel's, which would put every customer behind one
  address for the sign-in rate limits and the audit log. So the apps call the APIs directly on
  `api.` / `owner-api.` / `web-api.` / `admin-api.allmizan.live` (CORS allows the domain and its
  subdomains). Nobody visits these addresses.
- **Workspaces by host.** `mizan-system` holds `*.allmizan.live`. The app reads the workspace
  from the host name (`VITE_WORKSPACE_DOMAIN`), so routes need no `/c/<slug>` prefix and
  `/login` is the workspace's own sign-in. `/c/<slug>` on the old address keeps working.
- **Owners sign in in the owner panel** (`/owner/login`; `/login` on the apex forwards there). ADR-004 put
  the owners' sign-in on the ERP's `/login`; the ERP now has one address per workspace, so
  that page moved. The ERP's cloud `/login` without a workspace sends owners there.
- **Sessions per app.** On one origin the website, owner and admin panels share browser
  storage, so each app keeps its session under its own key (`mizan.session` for the ERP,
  `mizan.session.owner`, `mizan.session.admin`). Session handoffs between apps keep using the
  URL fragment (ADR-003); between the apex and a workspace they are still needed.
- **Links between apps** go through `appUrl()` and `workspaceUrl(slug, path)`
  (`shared/frontend/src/lib/urls.ts`), configured per deployment in `.env.production`.
- **DNS.** Wildcard certificates on Vercel need Vercel's nameservers, so the domain's DNS
  moves from Hostinger to Vercel (the registration stays at Hostinger). The Hostinger Reach
  mail records (SPF, DKIM, DMARC) are recreated on Vercel.
- **Reserved workspace names**: `www`, `dev`, `api`, `owner-api`, `web-api`, `admin-api`, `app`,
  `admin`, `owner`, `mail`, `docs`, `status`, `help`, `support`, `blog`, `static`, `assets`, `cdn`,
  `c`, `login`, `signup`, `store`, `storefront`, `billing`, `account`. A URL name must also be a
  valid DNS label (3–48 lowercase letters, digits or inner hyphens).
- **On-site installs** (ADR-005) are unchanged: one workspace, served at the server's address.

## Consequences
- One address for customers; each workspace has its own memorable address.
- Owner and admin users sign in again once (their session moved to a per-app key).
- The old `*.vercel.app` addresses keep working; links the apps generate use the new domain.
- A page of `/owner` or `/admin` takes one extra proxy hop on Vercel; API calls don't.

## Rollout (2026-11-12)
- Domains attached on Vercel: apex and `www` (308 to the apex) on `mizan-website`, `*.allmizan.live`
  on `mizan-system`, the four API hosts on their projects. Nameservers moved from Hostinger to
  Vercel; the Hostinger Reach mail records (SPF, DKIM ×2, DMARC) recreated on Vercel DNS.
- The owner API's `OWNER_APP_URL` (Paymob's return address) is `https://allmizan.live/owner`.
- Each app's `.env.production` holds the new addresses; the old `*.vercel.app` addresses keep
  working (the panels redirect `/` to `/owner/` and `/admin/`).
