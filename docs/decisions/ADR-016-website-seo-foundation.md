# ADR-016: The public website's SEO foundation

## Status
Accepted (2026-11-23). Built in `website/frontend` (pre-rendering, head data, English pages,
measurement), `deploy/server/nginx.conf` (status codes, robots, redirects), the website and admin
APIs (cookieless counters).

## Context
allmizan.live was a client-rendered SPA: every address answered the same empty `<div id="root">`
with one title and description, `/robots.txt` and `/sitemap.xml` returned that page, unknown
addresses answered 200 (soft 404s), the social image was an SVG, fonts came from Google, and the
site had no structured data, canonical or hreflang. The owner decided: Arabic first, English
versions of the key pages under `/en`, first-party cookieless measurement plus GA4 behind consent.

## Decision

### D1. Pre-rendered pages, hydrated in the browser
`npm run build` makes the browser bundle, then `vite build --ssr src/entry-server.tsx`, then
`scripts/prerender.mjs` renders every public page with `react-dom/static` (`prerenderToNodeStream`,
which waits for every lazy page) inside a `StaticRouter`, into `dist/<path>/index.html` with the
page's whole content and head. The browser hydrates it (`hydrateRoot` when the root says
`data-prerendered`); application pages (signup, onboarding, the developer portal) get the empty
shells `spa.html` / `dev.html` and mount as before. No headless browser is involved.

- Rules for code that renders on the server: no `window`/`localStorage` at module load (guard it);
  no locale-dependent formatting without a locale (`toLocaleString("en-US")`); entrance animations
  of the first page start from the drawn state (`useEntrance`), so the HTML is visible and matches;
  components that read browser state (`useOwner`) use a server snapshot.
- The page's language comes from its address (`LocaleScope` in `@/i18n`, `LangScope`), not from the
  saved choice, so the server and the browser render the same thing. `<html data-locale="url">`
  tells the shared i18n store not to apply the saved language on load.
- The app's JavaScript loads after the page's `load` event (the HTML is complete without it), with the
  page's own chunk alongside; heavy interactive parts are their own `lazy` chunks and Suspense
  boundaries, hydrated one at a time.
- The CSS rules a page uses are inlined at build time (`beasties`); the full stylesheet loads without
  blocking, for the pages opened next.

### D2. One typed module for every page's head
`src/seo/pages.ts` lists every public page (marketing, legal, blog, docs; Arabic and English) with its
title, description, social image, breadcrumbs and structured data; `src/seo/head.ts` turns it into
tags (`data-seo`, replaced by `SiteEffects` on client navigation, which loads the module lazily).
Structured data (`src/seo/jsonld.ts`, typed with `schema-dts`) uses only facts: Organization from
`features/legal/business.ts` (no `sameAs` until real profiles exist), WebSite (no SearchAction: the
docs search has no URL), SoftwareApplication with offers from `src/seo/plans.snapshot.json` (the live
plans API, refreshed by `npm run seo:plans`; no ratings), BreadcrumbList, BlogPosting (author: the
organization), FAQPage only for the FAQs shown on the page. Tested in `src/seo/__tests__/`.

### D3. Addresses
- Arabic at `/…` (unchanged), English under `/en/…` for the pages in `EN_PAGES` (`src/seo/paths.ts`).
  `hreflang` `ar`, `en`, and `x-default` pointing at the Arabic version of the same page. Internal
  links go through `@app/seo/LocaleLink` so an English page links to English pages where they exist.
- No trailing slash and no `/index.html`: both 301 to the canonical address. Unknown addresses are
  404 with the branded page (`404.html`, `en/404.html`). Moved addresses are in nginx's
  `$mizan_moved` map (the old `/features/<slug>` duplicates, a withdrawn post). `/dev/*` on
  allmizan.live 301s to dev.allmizan.live.
- `robots.txt` and the sitemap index (`sitemaps/pages.xml`, `blog.xml`, `docs.xml`, only canonical
  indexable pages, with hreflang). `lastmod` changes only when a page's rendered content changes
  (`src/seo/lastmod.json`, updated by `node scripts/prerender.mjs --update-lastmod`).
- Application pages answer `X-Robots-Tag: noindex` and stay crawlable so the header is seen. The
  ERP and workspace hosts answer `noindex` and a `Disallow: /` robots.txt; the APIs answer
  `noindex` and their own robots.txt (`deploy/server/asgi.py`). dev.allmizan.live has its own
  robots.txt and no sitemap: whether the portal is indexed is the portal's decision. When ADR-015's
  public storefronts ship on workspace hosts, those hosts need their own rules.

### D4. Assets
Self-hosted fonts (`scripts/build-fonts.py`: Google's woff2; the Arabic families keep only the basic
Arabic block, and Latin text inside Arabic uses the Latin families, Manrope and Cormorant Garamond;
variable files merged), `font-display: swap`, size-adjusted local fallbacks, one preloaded body font
per language. The page's font faces are inlined with its CSS, so they load before the first paint:
measured, deferring them gave a faster lab LCP (about 1.8 s) but a layout shift of 0.1 to 0.24 when the
fonts swap in, so they stay early. PNG social images per page type and language and
PNG icons (`scripts/og-images.py`, committed), a web manifest. Lenis and GSAP load only for a fine
pointer, when idle.

### D5. Measurement
- First-party, cookieless: `POST /analytics/event` on the website API adds one to a daily counter
  (`site_analytics_daily`: day, kind, name, path, language, referring host). No cookie (the CSRF
  cookie is not set on that answer, the browser sends it with `credentials: "omit"`), no IP, user
  agent or identifier stored; crawlers dropped by user agent; rate-limited in memory. Totals in the
  admin panel (Website page, `GET /admoon/website/analytics`).
- GA4 only if `VITE_GA4_ID` is set at build time, and only after the visitor accepts it in the consent
  banner (choice in `localStorage`, "Analytics settings" in the footer to change it). The same events
  go to GA4 under its recommended names. The privacy policy says so.

## Consequences
- Every public page must be in `src/seo/pages.ts` (the build fails if a page renders without an
  `<h1>` or its component isn't a lazy chunk). New English pages: add them to `EN_PAGES` and give
  them English copy.
- Shared code the website renders must stay safe to render in Node (D1 rules).
- Content changes should be followed by `--update-lastmod` and a commit of `lastmod.json`.
- After a release, run Google's Rich Results Test and URL Inspection on a few pages, and submit
  `https://allmizan.live/sitemap.xml` in Search Console.
