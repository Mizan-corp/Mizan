# Mizan Website

The public face of Mizan: landing, product, industries, pricing, blog, the user docs,
self-serve signup with the 3-step onboarding wizard, contact, the legal pages, and the
**developer platform** at `dev.allmizan.live`.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `npm run dev:website` → http://localhost:5174 (developer platform: /dev) | https://allmizan.live, https://dev.allmizan.live |
| API | `backend/` | `docker compose up website-api` → :8001 | https://web-api.allmizan.live/api |

- The API exposes `GET /platform/plans` and `POST /platform/signup` (rate-limited), and the
  developer portal's `/developers/*`. Signup creates the owner account and workspace, seeds
  sector demo data and returns a token.
- After onboarding the new owner lands in the **owner panel**, already signed in
  (`openWithSession` in `system/core/frontend/src/lib/handoff.ts`).
- "Sign in" goes to `/login`, which forwards to the owner panel's sign-in (`/owner/login`,
  ADR-008); owners come back through `/session`
  here: the website keeps its own copy of the owner's session (`mizan.owner_session`) to
  show "back to panel" and "sign out" instead of "get started" and "sign in".
  `/signout` clears it.

## Public pages, search engines and languages (ADR-016)

- **Pre-rendered.** `npm run build -w website/frontend` builds the app, then renders every public
  page into `dist/<path>/index.html` (`scripts/prerender.mjs`, with the renderer from
  `src/entry-server.tsx`); the browser hydrates it. Application pages (signup, onboarding, the
  developer portal) use the empty shells `spa.html` and `dev.html`. `npm run build:spa` skips the
  pre-rendering. Code the pages render must work in Node: see ADR-016 D1.
- **Head data in one place:** `src/seo/pages.ts` (title, description, canonical, hreflang, social
  image, structured data for every page). A new public page goes there and is a `lazy` page in
  `App.tsx`. After changing content, `node scripts/prerender.mjs --update-lastmod` (after a build)
  refreshes the sitemap dates in `src/seo/lastmod.json`; commit it.
- **Arabic and English.** Arabic at `/…`, English under `/en/…` for the pages in `EN_PAGES`
  (`src/seo/paths.ts`); the address decides the language. Link with `Link` from
  `@app/seo/LocaleLink` so English pages stay English.
- **Plans** in the structured data come from `src/seo/plans.snapshot.json`: refresh it from the live
  API with `npm run seo:plans -w website/frontend`.
- **Fonts and images:** self-hosted fonts (`scripts/build-fonts.py` writes `src/assets/fonts/` and
  `src/fonts.css`); social images and icons (`npm run seo:og`, Python Playwright, writes `public/og/`
  and `public/icons/`). Both are committed; neither runs in the image build.
- **Checks:** `npm test -w website/frontend` (paths, head data, structured data, and no unsupported
  marketing claims), and against a running build (the web image or nginx over `dist/`):
  `python3 scripts/crawl-check.py http://127.0.0.1:<port> [--browser]` (every sitemap URL 200 with
  its own title/description/canonical and one `<h1>`, hreflang both ways, 404s, 301s, robots,
  hydration without errors). After a release, run Google's Rich Results Test on a few pages.

## Measurement (ADR-016 D5)

- **Cookieless counters:** the site sends each page view and these events to `POST
  /analytics/event` (this API): `whatsapp_click`, `phone_click` (any `wa.me` / `tel:` link),
  `contact_submit`, `demo_request` (the contact form), `signup_start`, `signup_complete`. The API adds
  one to a daily counter per page, language and referring site (`site_analytics_daily`); nothing
  about the visitor is stored and no cookie is set. The Mizan team reads the totals in the admin
  panel, **Website** (`GET /admoon/website/analytics?days=`).
- **Google Analytics 4:** off unless `VITE_GA4_ID=G-…` is set at build time (in
  `frontend/.env.production`). Then a consent banner asks first; GA4 loads only after "Accept"
  ("Analytics settings" in the footer changes the answer). The same events go to GA4 as `contact`,
  `generate_lead`, `sign_up_start`, `sign_up`, and page views as `page_view`.

## Legal pages and business details

| Page | Route |
|---|---|
| Terms of Service · شروط الاستخدام | `/terms`, `/en/terms` |
| Privacy Policy · سياسة الخصوصية | `/privacy`, `/en/privacy` |
| Refund & Cancellation Policy · سياسة الاسترداد والإلغاء | `/refund-policy`, `/en/refund-policy` |

- Text: `frontend/src/features/legal/documents.ts`, Arabic and English side by side; the
  page layout is `LegalPage.tsx`. Keep them true to how Mizan works (no automatic
  renewal, the cookieless counters and GA4 only with consent, the providers actually used) and,
  when they change, update
  `BUSINESS.effective`.
- **The seller's details** (name, city, phone/WhatsApp) live only in
  `frontend/src/features/legal/business.ts` and are used by the legal pages, the footer,
  the contact page and the About page. Paymob checks them against the merchant account.
- Linked from the footer, the signup form ("by creating an account you agree…") and the
  owner panel's pay dialog (terms and refund policy).
- The contact form has no mailbox behind it: it opens WhatsApp with the message written out.

## The developer platform (ADR-007 D6)

`frontend/src/features/developers/`, served at the root of `dev.*` hosts and under `/dev`
elsewhere (`paths.ts`). **English by default**, Arabic on request: its own language choice
(`mizan.dev_locale`), so the website keeps its Arabic default.

- `DevHome.tsx`: what developers can build (whole activities, modules, themes) and where to start.
- `AuthPage.tsx`, `PortalShell.tsx`, `TeamsPage.tsx`, `TeamPage.tsx`, `TokensPage.tsx`,
  `AccountPage.tsx`: the portal (developer accounts, teams and members, signing keys with
  Mizan's certificates, CLI tokens, password), over `/developers` on this API
  (`backend/website_api/routers/developers.py`; logic in `system/core/backend/app/platform/developers/`).
- `devDocs.en.ts`, `devDocs.ts`: the developer docs in English and Arabic, rendered by the docs
  components (`features/docs/`). Keep them true to the code: the validator
  (`app/framework/manifest.py`), `/ext/v1`, webhooks, the CLI (`sdk/python`).
- The SDK wheel is built into `public/sdk/` by the release workflow and served at
  `dev.allmizan.live/sdk/`.

