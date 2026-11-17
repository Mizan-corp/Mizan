# ADR-015: The website builder and storefront

## Status
Accepted in principle by the owner on 2026-11-17 (answers recorded below); not built. Replaces the
current `storefront` module, which the module audit of 2026-11-17 found not production-ready
(docs/PRODUCTION_READINESS.md). No workspace has the storefront enabled (checked in production on
2026-11-17), so nothing has to be migrated.

## Context
Mizan's `storefront` module today is one public shop page per workspace
(`/storefront/{slug}/...` on the API, `PublicStorefrontPage.tsx`) with an admin screen. The audit found:
public order tracking that exposes customers' names and addresses to anyone who guesses a 4-digit
order number; online orders that never touch stock, cash or the ledger; fake Fawry and card payment;
money stored as floats; no validation of checkout; no tests of checkout.

The owner wants far more than a fix: a website builder in the spirit of WordPress with Elementor and
the Astra customizer, and Wix, merged, where a workspace can design its whole public site, install,
make and customize themes, and sell online, with the ERP managing it.

What exists that this builds on:
- ERP themes (ADR-010 D3): design tokens (colours, fonts, radius, shadows) for the ERP's own screens,
  theme packages (`.mzm`, `kind: "theme"`), the SDK's `mizan theme new|check|package`.
- The marketplace and developer platform (ADR-006 phase 7, ADR-007, ADR-012).
- The screen designer (ADR-006 phase 5) for ERP forms.
- The ledger (ADR-014), the sales service, stock reservations are new.
- Paymob for Mizan's own subscriptions (ADR-004), WhatsApp nowhere yet.

## Decision

### D1. Addresses
- **Every workspace's ERP lives at `<workspace>.allmizan.live/admin`**, storefront or not: one rule,
  no URL that moves when the storefront is switched on. The site designer (the studio) is a separate
  full-screen app at `/admin/studio`.
- **The root `<workspace>.allmizan.live/` is the public site** when the storefront is enabled; otherwise a
  small branded landing page with the staff sign-in link.
- **Custom domains:** an owner can point their own domain (`shop.example.com` or the apex) at the site,
  with automatic HTTPS through Cloudflare for SaaS (custom hostnames). `/admin` on a custom domain
  redirects to the workspace's own `allmizan.live` address (staff sessions stay on Mizan's domain).
- Migration: old ERP links (bookmarks, installed PWAs, print and handover links, emails) redirect to
  `/admin/...`; the ERP's router, `appUrl()` / `workspaceUrl()`, the service worker scope and the PWA
  manifest move to the `/admin/` base. Reserved paths on the root: `/admin`, `/api`, `/_m` (site
  runtime assets), `/.well-known`.

### D2. Security of one origin shared by a public site and the ERP
The site and the ERP share an origin, so anything running on the site could act as the staff member
signed in to `/admin` in the same browser. Therefore:
- **The ERP session moves to an HttpOnly, Secure, SameSite=Lax cookie with `Path=/admin`** (and the
  API's cookie), not `localStorage`/`sessionStorage`; CSRF tokens stay (they already exist).
- **Strict Content-Security-Policy on both:** the ERP allows only its own scripts; site pages allow only
  Mizan's site runtime and the declared integrations (D9).
- **Workspace users can't add JavaScript.** Pages are built from blocks; custom CSS is allowed (no
  `url()` to other hosts, no `@import` of other hosts, sanitized); custom HTML blocks are sanitized
  (no scripts, no event handlers, no `javascript:` URLs, no iframes except allow-listed embeds such as
  YouTube and Google Maps).
- **Developer themes and blocks may ship JavaScript, managed by the SDK** (owner's decision): developer
  code never runs in the site's origin. It runs in a sandboxed iframe served from a separate origin
  (`<id>.sandbox.allmizan.live` or a dedicated domain), `sandbox="allow-scripts"` without
  `allow-same-origin`, talking to the page only through the SDK's message bridge, which exposes a
  declared, versioned API (read the block's settings, the public catalogue, add to cart, track an
  event) and nothing else. The SDK builds, bundles, scans and signs the code; the marketplace reviews it
  before listing; the bridge enforces the permissions declared in the package's manifest. A package
  without JS needs no sandbox.
- **Shoppers are not users.** Shopper accounts live in their own table and their own session (cookie
  `Path=/`, scope `shopper`); a shopper token never opens the ERP and an ERP token never acts as a
  shopper (the ERP already refuses scoped tokens, #154).
- Public routes bind exactly the workspace of the host (or custom domain) and expose only published,
  public fields (never cost prices, internal ids where avoidable, other shoppers' data); rate limits on
  sign-in codes, checkout, coupon checks and search; order tracking only with the shopper's session or
  a private random token (≥128 bits).

### D3. What a site is
A full website, of which the shop is one part: pages, menus, blog, forms, and commerce (catalogue,
product, cart, checkout, account). Activity blocks come later through the same engine: restaurant menu
and table ordering, clinic and salon booking, hotel rooms, school registration.

### D4. The builder
- **Sections → columns → blocks** (Elementor style): drag to reorder, per-device settings (desktop,
  tablet, mobile: visibility, spacing, size, layout), reusable sections and global blocks.
- **A free-form canvas section** (Wix style) where blocks are positioned freely, with its own mobile
  arrangement; the rest of the page stays responsive.
- **Global styles** (Astra customizer style): colours, typography scale, buttons, forms, spacing,
  container width, header and footer builders with layouts, sticky and transparent headers.
- Undo/redo, autosave drafts, preview on devices, publish, revision history and rollback, scheduled
  publishing later.
- The page is stored as a JSON tree (block type, settings per device, children, content per language);
  the same tree renders in the studio and on the server.

### D5. Themes (full template kits)
A site theme contains: global styles, header and footer, templates (home, product, category/collection,
search, cart, checkout, account pages, blog list and post, static page, 404), demo pages and demo
content, fonts and images. A workspace can:
- **install** a theme (Mizan's, from the marketplace free or paid, or from a signed file);
- **apply** it, switching without losing content: content lives in pages and the catalogue, templates
  and styles come from the theme; a switch maps the new theme's templates onto existing pages and
  keeps a backup of the previous theme's customizations;
- **customize** any part (styles, templates, header and footer) with the studio; customizations are a
  layer over the theme so a theme update can be applied;
- **make** a theme: "save as theme" in the studio, or in code with the SDK
  (`mizan site-theme new|check|package`, a new package kind `site_theme`), validated (structure, known
  blocks, sanitizing, contrast, size limits, D2 rules for JS).
Mizan ships 2–3 themes in the first release (general shop, fashion, food).

### D6. Rendering
Public pages are rendered on the server to HTML from the page tree and the theme (no SPA needed to read
a page), with a small site runtime for interactive blocks (cart, variant picker, filters, sliders),
then cached at Cloudflare's edge and purged on publish or on catalogue changes. SEO: per-page and
per-product titles and descriptions, canonical URLs, `hreflang`, sitemap and robots, Open Graph and
product structured data, clean URLs (`/p/<slug>`, `/c/<slug>`), redirects. The studio itself is a React
app inside `/admin`, previewing with the same server renderer. Implementation (to confirm in step S1):
a renderer module in the API (Python, Jinja2 in a sandboxed environment for theme templates), served by
a new `site` service behind the tunnel for the root and custom domains.

### D7. Languages
Arabic and English first (each page, block text, product, category and menu can have both; visitors
switch; RTL/LTR from the language), designed for any number of languages later (content keyed by
language code, not by two fixed columns).

### D8. Commerce
- **Payments go to the merchant.** Each workspace connects its own Paymob account (later Fawry and
  InstaPay) in the storefront settings; Mizan never holds shoppers' money. Cash on delivery works with no
  account. Payment callbacks are signed and idempotent (as ADR-004's Paymob for subscriptions).
- **Stock:** the owner picks the branch (or an "online" warehouse) that fulfils online orders; the site
  shows its available stock. Placing an order **reserves** the quantities (a new reservation table:
  available = on hand − reserved), with a time limit for unpaid card orders; **confirming** turns the
  order into a real sale through the sales service (stock out, cash or receivable, VAT, ledger,
  ADR-014); cancelling releases the reservation; a refund is a sale return.
- Orders: per-workspace numbers from a counter; statuses with an allowed-transitions table (new →
  confirmed → preparing → shipped → delivered; cancelled; returned), every change audited, shopper
  notified.
- Prices, discounts, VAT and shipping are always computed on the server (the cart is re-priced at
  checkout); coupons with limits, atomic use counts and generic error messages.
- **Shipping & payments** settings: delivery zones (governorates, cities, areas) with fees and minimums,
  pickup points, couriers later (Bosta, Mylerz, Aramex), payment methods per zone.

### D9. Shoppers
Sign-in by **phone with a one-time code over WhatsApp (or SMS)** and **Google sign-in**; guest checkout
is not in the owner's list (open question Q3). A shopper has a profile, addresses, order history and
wishlist; a shopper is linked to (or creates) the workspace's CRM customer. Codes are rate-limited per
phone and IP, short-lived and single-use.

### D10. Messages to shoppers: WhatsApp first
Order confirmation, status changes and sign-in codes go by **WhatsApp Business (Meta Cloud API)** first,
email only for receipts (Brevo's free 300 a day is shared by every workspace). Open question Q2: one
Mizan WhatsApp sender for all shops, or each workspace connects its own number. Per-message cost is
recorded per workspace for billing.

### D11. How it is sold: every option, decided in the admin panel
The admin panel gets storefront settings per plan: off, included, or paid add-on with its monthly price;
limits per plan (pages, published products, storage, staff seats in the studio, custom domains,
languages, WhatsApp messages included); and marketplace theme revenue share. Plan gating
(`plan_gating.py`) enforces them; the owner panel shows and sells the add-on.

### D12. ERP side panel (the storefront module's screens)
All eight areas; the first release (D13) builds the first five, the rest follow:
1. **Orders**: list, filters, detail, confirm, prepare, ship, deliver, cancel, refund, print, notes.
2. **Shoppers**: accounts, addresses, orders, block, link to the CRM customer.
3. **Catalogue online**: published products, online price, photos, SEO text, categories, collections,
   stock shown.
4. **Shipping & payments**: zones and fees, payment methods, the merchant's Paymob account.
5. **Marketing (coupons)**: coupons and offers first; gift cards and campaigns later.
6. **CRM**: customers across shop and POS, segments, notes, follow-ups, abandoned carts.
7. **Content**: pages, blog, menus, media library, forms and submissions, redirects, SEO settings.
8. **Analytics**: visits, conversion, top products, sources.
Plus the **Studio** (D4, D5) and **Site settings** (domain, languages, integrations: Facebook Pixel,
Google Analytics/Tag Manager, TikTok pixel, WhatsApp chat button, by ID only).

### D13. Order of work (each step its own PRs, with tests)
- **S0. Close the current storefront's holes** now, before any redesign: hide the module from the
  catalogue (status `beta`, not offered) until S4 ships, so no workspace can enable the leaking version.
- **S1. Foundations:** ERP to `/admin` (router base, redirects, service worker, PWA, links, print and
  handover URLs, tests); HttpOnly cookie session with `Path=/admin`; CSP for the ERP; the `site`
  service on the root of workspace hosts; plan settings in the admin panel (D11).
- **S2. Page engine:** page tree model and storage (pages, revisions, languages), the block registry
  (layout, text, image, gallery, video embed, button, icon list, spacer, HTML (sanitized), form later),
  the server renderer, edge caching and purge, SEO basics.
- **S3. Studio:** sections/columns/blocks editor with per-device settings, global styles, header and
  footer builders, undo/redo, autosave, preview, publish, revisions; the canvas section.
- **S4. Shop end to end:** catalogue online (publish, slugs, photos, SEO), product/category/search/
  cart/checkout/account templates and blocks, stock reservations, orders becoming real sales, COD and
  the merchant's Paymob, shoppers (WhatsApp/SMS code, Google), shipping zones, coupons, order
  notifications by WhatsApp, the five ERP screens of D12. Two or three Mizan themes.
- **S5. Themes as packages:** install/apply/switch/customize layers, "save as theme", the SDK's
  `site_theme` kind and validator, marketplace listing; developer JS in the sandbox (D2).
- **S6.** Custom domains; CRM; content (blog, forms, media library, menus, redirects); marketing
  (gift cards, campaigns); analytics.
- **S7.** Activity blocks: restaurant menu and table ordering, clinic and salon booking, hotel rooms.

## Open questions (to ask the owner before the step that needs them)
- Q1 (S4): which couriers to integrate first, and whether cash-on-delivery limits apply per zone.
- Q2 (S4): one Mizan WhatsApp sender for all shops, or each workspace's own number (needs Meta
  Business verification per workspace); SMS fallback provider.
- Q3 (S4): guest checkout (not chosen on 2026-11-17): allowed or not.
- Q4 (S5): marketplace revenue share for paid themes; review process and SLA.
- Q5 (S1): on-site installs (ADR-005): does the site run there too, and on which address.
- Q6 (S6): does the CRM replace or extend `contacts` customers (one customer record across POS and shop
  is assumed).

## Alternatives considered
- **Keep the ERP at the root and put the site on another subdomain** (`shop.<workspace>`): no shared
  origin problem, but the owner wants the root to be the site and the ERP at `/admin`.
- **Allow custom JavaScript from workspace users (WordPress style):** would require moving the ERP to
  its own origin; refused for now (D2). Known integrations by ID cover pixels and chat.
- **A browser-only SPA for public pages:** simpler, but weak for search engines and slow first paint.
- **An external builder (WordPress/WooCommerce, Shopify) synced with Mizan:** two systems, syncing,
  tenant isolation lost; Mizan is a modular monolith (ADR-001).

## Consequences
- Every workspace's ERP address changes once (to `/admin`), with redirects.
- Staff sessions become HttpOnly cookies, which also hardens the ERP against XSS in general.
- A new public-facing service with its own caching, rate limits and abuse handling must be operated.
- WhatsApp messages and custom domains add per-workspace costs that billing must carry (D11).
