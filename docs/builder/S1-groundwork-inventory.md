# S1 groundwork inventory: moving the ERP to `/admin`

Status: analysis, verified against `master` on 2026-11-23. Companion to ADR-015 (step S1)
and ADR-016. Nothing here is implemented; this is the exact file inventory and the order of
changes so S1 lands as small, reviewable PRs.

ADR-015 S1 scope (verbatim): "ERP to `/admin` (router base, redirects, service worker, PWA,
links, print and handover URLs, tests); HttpOnly cookie session with `Path=/admin`; CSP for
the ERP; the `site` service on the root of workspace hosts; plan settings in the admin panel
(D11)." This document covers the ERP move and its ripple effects; the `site` service itself
is S2 territory, and plan settings are an admin-panel change tracked separately.

## 1. Where the ERP is served today

- `deploy/server/nginx.conf`: the `default_server` block (`server_name _;`) serves the ERP
  SPA from `/srv/web/system` at the **root** of every host that is not `allmizan.live`,
  `dev.allmizan.live` or `www.allmizan.live` — that means every workspace host
  (`<slug>.allmizan.live`) and `app.allmizan.live`. `location / { try_files $uri /index.html; }`.
- The apex already uses `/admin/` for the **platform admin panel**
  (`location /admin/ { root /srv/web/panels; try_files $uri /admin/index.html; }`).
  After S1, `/admin/` means the workspace ERP on workspace hosts and the platform admin
  panel on the apex. That is consistent per host, but the collision deserves one line in
  ADR-015 or a comment in the nginx config so nobody "fixes" it later.
- `system/frontend/vite.config.ts`: `base` comes from `VITE_BASE`, default `/`.
  The move is `VITE_BASE=/admin/` plus routing — no source restructure.

## 2. What already follows the base automatically

- `system/frontend/src/main.tsx`:
  - Service worker: `navigator.serviceWorker.register(`${base}sw.js`, { scope: base })`.
  - Router: `<BrowserRouter basename={import.meta.env.BASE_URL}>`.
  - Both follow `VITE_BASE` with no code change.
- `system/frontend/public/sw.js`: computes `BASE` from its own URL and scopes all cache
  keys off it (`mizan-shell-v4`). A build served from `/admin/` self-adjusts.
- `system/frontend/public/manifest.webmanifest`: must be checked for `start_url`/`scope`
  (PWA install from `/admin/`).

## 3. The service-worker migration is the dangerous part

Existing users on workspace hosts already have a service worker registered at scope `/`
(from today's root-served ERP). After S1, the root serves the `site` service, but the old
SW still intercepts every same-origin navigation: its handler is network-first, and on any
network failure it serves the cached **ERP shell** for site pages. Worse, its
`fetch` handler caches successful navigations, so the ERP shell can shadow the site.

S1 therefore needs an explicit SW migration, in this order:

1. The `site` service at the root serves its own `sw.js` at `/sw.js` (even a minimal one)
   that calls `self.registration.unregister()` and deletes the old `mizan-shell-*` caches —
   or claims the root scope for the site. Without this, returning visitors can get the ERP
   shell instead of their storefront.
2. The ERP's SW moves to scope `/admin/` (automatic via `BASE_URL`, above) and `CACHE`
   is bumped so old root-scope caches are dropped on activate.
3. E2E coverage: a browser test that loads the root with an old SW present and asserts the
   site wins. Today there is no such test; `system/frontend/src/main.tsx` registers the SW
   in PROD only, which is why this has never bitten in CI.

## 4. Links and handoffs that assume the ERP lives at the root

`shared/frontend/src/lib/urls.ts` is the single source: `workspaceUrl(slug, path)` builds
`https://<slug>.<VITE_WORKSPACE_DOMAIN><path>`, and today every caller treats `/` as the
ERP. After S1 the root is the site, so every ERP-bound link must target `/admin/...`.

Consumers to update (found by searching `appUrl`/`workspaceUrl`):

- `shared/frontend/src/lib/handoff.ts` — `openWithSession`/`openWorkspaceWithSession` pass
  the access token in the URL fragment (`#session=...`). The target paths become
  `/admin/...`; the fragment mechanism itself stays (cross-host: apex → workspace host).
- `owner/frontend/src/lib/open.ts`, `pages/Workspace.tsx`, `pages/Login.tsx`,
  `lib/session.ts`, `Shell.tsx`, `Tour.tsx` — the owner panel's "open workspace" entries.
- `website/frontend/src/features/session/SessionRoutes.tsx`,
  `features/marketing/SignupPage.tsx` (post-onboarding handoff),
  `features/marketing/MarketingLayout.tsx`, `features/developers/DevHeader.tsx`,
  `App.tsx`.
- `admin/frontend/src/Shell.tsx`, `pages/WorkspaceDetail.tsx` (impersonation opens the ERP).
- `shared/frontend/src/features/billing/PricingPage.tsx`.
- Inside the ERP itself: `system/frontend/src/features/auth/LoginPage.tsx`,
  `features/tenant/TenantScopeLayout.tsx`, `components/AppShell.tsx`, `App.tsx`
  (mostly relative links that follow the basename — verify, don't assume).
- `system/frontend/src/lib/__tests__/workspace-host.test.ts` — update expectations.

Recommended shape: add `erpUrl(slug, path)` (or a `workspaceUrl(slug, path, { area: "erp" | "site" })`
parameter) in `urls.ts` so the `/admin` prefix lives in exactly one place, then migrate the
callers. That keeps the later custom-domain work (S6) from touching every caller again.

## 5. Session: bearer + cookie today, `Path=/admin` cookie wanted

- `shared/backend/app/platform/auth/routes/auth.py` `/auth/login` already sets an HttpOnly
  `access_token` cookie — **with `path="/"`** — and also returns the token in the body.
- The frontend keeps the token in `localStorage` (`shared/frontend/src/stores/auth.ts`)
  and sends it as a Bearer header (`shared/frontend/src/lib/api.ts`).

Moving the cookie to `Path=/admin` is a one-line change, but S1's intent is cookie-based
auth for the ERP (otherwise the path is cosmetic). That switch has real blast radius:

- `shared/frontend/src/lib/api.ts` must send `credentials: "include"` and stop depending on
  the Bearer header for browser sessions.
- Every mutating request then needs the CSRF header: `shared/backend/app/middleware.py`
  implements double-submit (`csrf_token` cookie + `X-CSRF-Token` header) and currently
  **exempts Bearer-authenticated requests**. Switching the ERP to cookie auth moves all of
  its mutating traffic into CSRF-checked territory. The API client must read the CSRF
  cookie and echo the header; the exempt-suffix list (`/auth/login`, `/auth/print-token`,
  …) and the `/api` mount-prefix stripping in `_script_rel_path` must be re-checked.
- `adoptHandedOffSession` in `main.tsx` sets the localStorage token from the fragment; with
  cookie auth it should instead exchange the fragment token for the cookie (or keep Bearer
  for the handed-off session — decide explicitly in the S1 PR, don't let it emerge).
- E2E: `e2e/api/test_auth.py`, `test_sessions.py`, `test_read_only.py` touch this area.

## 6. Print and handover URLs

- Printing uses a short-lived `/auth/print-token` (`shared/backend/app/platform/printing/`),
  consumed from `system/frontend/src/activities/general/modules/pos/PosPage.tsx` and
  `shared/frontend/src/lib/api.ts`. Print windows/URLs must keep working under the new base
  and under cookie auth (the print-token exists precisely so a new window can authenticate
  without the session — verify it stays CSRF-exempt and works from `/admin/`).
- Session handoff (`handoff.ts`, §4) is the other "handover" path.

## 7. CSP for the ERP

- No CSP exists for the ERP today: a search for `Content-Security-Policy` across the repo
  finds only ADR-015 itself and one healthcare media route. Headers are set in the nginx
  includes (`/etc/nginx/mizan-common.conf`, `mizan-panel-headers.conf`, referenced by
  `deploy/server/nginx.conf`; the include files themselves live on the server, not in the
  repo — locating or importing them is an S1 task) or can be added in backend middleware.
- Constraints to respect when writing the policy: the Vite build (hashed assets, no inline
  scripts expected — verify), `sw.js`, external file storage (uploaded files on Vercel Blob
  per the sw.js comment), fonts, and the dev-server proxy. Start report-only, then enforce.

## 8. Open questions that gate S1

- **Q5 (ADR-015)**: on-site installs (ADR-005) — does the site run there too, and on which
  address? The on-prem server (`shared/backend/app/onprem/server.py`) also uses
  `/auth/print-token`; the ERP move on on-prem installs is undecided and **owner input is
  needed before the S1 PRs touch shared routing**. Until then, keep the move
  Cloud-only-behind-config so on-prem behaviour is unchanged.
- Cookie auth vs Bearer for browser sessions (§5) — a design decision to record in the S1 PR
  description, since ADR-015 names the cookie but not the client-side switchover.
- `/admin/` naming collision with the platform admin panel on the apex (§1) — document, or
  pick another path before it is load-bearing in bookmarks and SW scopes.

## 9. Suggested PR slicing for S1

1. `erpUrl()` helper in `urls.ts` + migrate all ERP-bound callers (no behaviour change yet:
  still served at root, prefix configurable). Tests updated.
2. Serve the ERP at `/admin/` on workspace hosts (VITE_BASE, nginx, manifest) with the SW
  migration from §3. E2E: old-SW-at-root test, login, a print flow.
3. Cookie session `Path=/admin` + CSRF-checked API client. E2E: session and read-only suites.
4. CSP report-only for the ERP, then enforce after a soak period.
5. Plan settings in the admin panel (D11) — independent, can start any time.

Each PR is small, reversible, and deployable without the others; none requires the `site`
service to exist until PR 2's routing flips the root, which can ship behind the same nginx
change that keeps serving the ERP at root until the site service is ready.
