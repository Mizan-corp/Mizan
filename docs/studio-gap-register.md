# Studio Gap Register (feat/studio-render-parity)

Durable register of every capability gap discovered while rebuilding a real
site (Wirya) through the Studio UI only. Each gap is a missing Studio
capability, not a site-specific shortcut. Items move to **Done** only when the
capability is editable through the Studio UI, verified live, and covered by
tests. This file is the acceptance checklist; nothing here may be silently
dropped or marked done by narration alone.

Conventions: "per-device" means the responsive authoring model (switch
desktop/tablet/mobile in the editor, edit each view manually, unset values
inherit from desktop).

## User architecture decisions (2026-11-25, controlling)

These are the user's own decisions (WhatsApp, EET), recorded verbatim in
English. They control scope and module boundaries; where an earlier note in
this file conflicts, these win. The coordinator's 17:37 proposal list of
extra Website-managed areas (SEO, domains, cookie policies, notification
rules, etc.) was NOT approved by the user and is not scope; the user's
17:38 boundary below supersedes any part of it that mixed UI settings into
the ERP module.

1. **Data ownership (17:30).** Categories must be implemented from the
   Inventory module; all images, descriptions, and content are managed
   THERE. Studio controls presentation only. No static category pages with
   copied data, no duplicated catalog.
2. **Dynamic product page (17:32).** Product pages must NOT be authored one
   by one. One template is designed once in Studio and applies to every
   product; each product has an ID that determines its URL.
3. **Module rename + ownership (17:33).** The frontstore module is renamed
   **Website**. When enabled, its tab manages orders, published products,
   and all website-related attributes, instead of those living in
   Inventory.
4. **Pages in Website (17:36).** Pages are managed from the Website module
   too.
5. **Studio launch UX (17:37).** Choosing to edit a page from Website opens
   a NEW FULL BROWSER TAB with standalone Studio and that page loaded — not
   Studio embedded inside the ERP interface/frame.
6. **UI vs non-UI boundary (17:38, controlling).** ALL website UI/design
   work belongs in Studio; everything non-UI belongs in the ERP module.
   The ERP manages page records/publication, data, and behavior config;
   appearance (layout, header/footer, menus, notification surfaces, any
   visual editing) is Studio-only. No website visual-editing panels in the
   ERP.
7. **Cross-module website integration (17:41).** The Website module manages
   the data going TO and FROM the website for ANY other module, not only
   the catalog: e.g. Help Desk services can be hosted on the website, and
   Website manages that bidirectional flow. Each module stays the source of
   truth for its own data; Website owns its exposure and flow on the site.
8. **Standing constraints carried forward.** Discovering missing Studio
   features while rebuilding Wirya IS the objective; every gap becomes a
   reusable UI-editable feature, never Wirya-specific code. Site authoring
   goes through the Studio UI only (original Wirya source assets; no
   hand-authored HTML/CSS/SVG, no DB/API page seeding). Responsive
   authoring is per-device with desktop inheritance.

## Done this branch (verified live, tests green)

| Area | Capability | Commits |
|---|---|---|
| Header composition | Row align (start/center/end/between/around/evenly) + precise gap slider 0-64px via `--row-gap` | e04f228 |
| Header per-device | Tablet/mobile overrides for density, hide search, hide bar, with desktop inheritance; visitor media classes `mz-t-*` (769-1024px) / `mz-m-*` (<=768px); mobile hide-bar also drops bar links from the menu sheet | 90be7e2, 6ecefe2 |
| Base CSS | Responsive columns media block kept last in `_BASE_CSS` (test pin) | 7f7cd91 |
| Search (data) | Public page `?q=` filters repeat items by case-insensitive substring on rendered display text; blank keeps all | 7e06431 |
| Search (wiring) | Header search form targets a UI-editable `search_target` header setting; the GET form submits `q` to that page. Verified by real typing + submit in the browser: header on wirya-home -> products-cd-e2e?q=... -> filtered items | pre-existing + 7e06431 |
| Search (empty state) | Zero-match query renders a localized (en/ar) "no results for q" text node instead of pruning the section; query-less pages keep the old prune behavior | 8083e86 |
| Search (native E2E) | Real mouse click focus + typed text (Input.insertText) + native Enter key AND a genuine mouse click on the submit button both submit the header form and land filtered on the target page (q=شاشة → 1 item; q=عرض → 2 items). Replaces the requestSubmit harness | live 2026-11-25 |

## Open gaps

### Header / theme composition
1. **Per-device alignment, reorder, and gap.** `header.tablet` / `header.mobile`
   currently expose only `density`, `hide_search`, `hide_bar`. Row align,
   element order, and precise gap must also be settable per device.
2. **Arbitrary header sizing and colors.** Height, padding, background, text
   and accent colors beyond the fixed presets are not editable in the UI.
3. **Search scope is display-field-only.** `?q=` matches only the repeated
   heading/display field. Full searchable data scope (descriptions, SKUs,
   other typed fields) is not yet searchable; widening needs a consent and
   exposure review before more provider data is matchable.

### Catalog / navigation (user architecture constraint, 2026-11-25)
The Inventory module owns categories and all product data (names, images,
descriptions). Studio binds to that data and controls presentation only;
no static category pages with copied data, no duplicated catalog.

4. **Category destinations.** Menu/bar items need link destinations that
   resolve to category-filtered collection pages. Product->category linkage
   (Product.subcategory_id) is a new public projection not named by consent
   wording v0-v3 (they cover name, plus price/image under display consent).
   Resolved 2026-11-25: this is implementation design within the user's
   explicit 17:30 category request — extend the explicit UI publication
   consent accurately (v4, same reversible pattern as v1/v2), scoped to
   published records only. Not a user-facing question.
5. **Dynamic product-detail pages.** One Studio-authored template applies
   to every product; the product id selects the record from the URL. Item
   bindings today pin a fixed `item_key` per element; the extension is a
   "current item" binding mode resolved from the route. The consent gate
   (`read_scoped_item`) already refuses unconsented records, so URL-selected
   reads stay inside the projection. Resolved 2026-11-25: extend the consent
   wording accurately to cover URL-selected current-record retrieval
   (scoped published records only); route shape is routine architecture —
   choose a consistent existing convention and document it here. Category
   pages should follow the same template model once (4) lands.

### Locale
Locale switch is DONE and PROVEN LIVE end-to-end (8094ec2, proof
2026-11-25): bilingual page `bilingual-proof-e2e` authored entirely
through the Studio UI (New page form, Arabic heading typed in the
inspector, Arabic title via the per-language title editor, saved,
published, made public). Visitor: default render ar/rtl with Arabic title
+ heading and an "English" switch link; `?lang=en` renders ltr English
title + heading with an "العربية" switch link to the bare canonical;
hreflang alternates [ar, en] on both. `?lang=` validated against the
page's languages; hidden lang input keeps language across searches.

SCOPE OF THIS PROOF (standing distinction): the bilingual milestone is
page content + direction only. The site chrome (header/footer) keeps its
authoring language on both renders — the English render still shows the
Arabic header/footer. Whole-site chrome translation is NOT accepted as
done and is a separate open capability (chrome copy is currently
single-language per site).
Open: the editor chrome preview does not render the new switcher; chrome
per-language copy is not yet authorable (see above).

### Assets
6. **Original source-asset workflow.** Site authoring must use the original
   Wirya source assets through the UI (upload/media library), never
   hand-authored HTML/CSS/SVG or DB/API seeding. The hosted test host also
   refuses uploads (no blob storage) — that limitation must stay visible.

### Website module (user decisions 3-6 above)
13. **Rename frontstore -> Website** with its tab managing orders, published
    products, website-related attributes, and pages (non-UI records and
    behavior config only). Source-ground existing IDs/contracts/migrations
    before semantic changes; keep Inventory as the product/stock source of
    truth; no duplicated catalog.
14. **Studio launch from Website** opens a new full browser tab with
    standalone Studio and the selected page loaded; workspace/page context
    and auth must cross the launch safely. Not embedded in the ERP frame.

### Module capabilities (unimplemented module surface)
7. **Cookies consent.** Module capability must be real consent behavior, not
   decorative UI.
8. **Notifications UI blocks.** Real notification surface per the module
   semantics.
9. **Mobile app bottom panel.** Per `app-shell.tsx` source semantics.

### Verification / environment
10. **Desktop/LAN verification** is parked by user decision (workspace-scoped
    branding only).
11. **Screenshot capture hang** recurs intermittently in the CDP harness;
    unresolved flake, worked around with fresh-target captures.
12. **Combined pytest runs** of the whole backend test directory show
    cross-file isolation failures (9) unrelated to individual files; run
    affected files individually for signal.

## Execution order for the remaining scope (2026-11-25)

Dependency-ordered. Each phase lists what is verified vs pending; nothing
moves to Done without the evidence named in this file.

**Phase 1 — verification hardening (no user-visible scope).** DONE
2026-11-25 (45a119b, 6490db9). Native Enter AND genuine mouse-click
search-submit E2E both proven live on the visitor site (fresh screenshots
reported); vite.preview.config.ts committed.

**Phase 2 — consent/publication foundation (blocks the catalog work).** DONE
2026-11-25 (a5ad2a0 + 46c0f9a). Consent schema v4 extends the explicit UI
publication consent (same reversible pattern as v1-v3) to cover
product->category linkage, URL-selected current-record retrieval and an
optional description display field, scoped to published records only.
Grounded in the user's 17:30/17:32 requests. Wording, gate tests,
revocation tests and docs/studio-consent-scope-v4.md shipped.
Verification boundaries (exact commands):
- Backend: pytest per test FILE (shared/backend/tests): writer 5,
  scoped-item 14, revocation 5, consent-v4 12 green; runtime/bindings/
  repeats/card_repeats/typed_fields/projection/scalar_gate/core_site/
  card_provider/card_runtime/multi_card all green individually.
- Frontend: single `npx vitest run` in system/frontend = 51 files,
  293 tests: 291 passed, 1 skipped, 1 failed. The one failure is
  treerender.test.ts "wraps the page in one mz-section", verified
  pre-existing at clean HEAD via git stash (not from v4 work). tsc
  --noEmit clean (separate command).
ACCEPTANCE DEBT (open, NOT exempted): the 9 whole-directory pytest
cross-file isolation failures and the treerender failure must be actually
diagnosed and resolved (or individually re-verified as fixed) before any
final overall acceptance claim; "pre-existing" is a temporary label, not
an exemption.

**Phase 3 — dynamic product template + category destinations.** IN
PROGRESS 2026-11-25. Route shapes (documented per plan):
- Product detail: `/site/{slug}/{page_path}/p/{product_uuid}` — the page
  at page_path is the single Studio-authored product template; the third
  segment pair selects the record. The existing (host, slug, page_path)
  activation row governs, so the template's per-page publish approval
  covers its detail URLs (the v4 consent wording names this behavior).
- Category: `/site/{slug}/{page_path}/c/{category_uuid}` — same model;
  the page is the category template with a route-filtered product list.
Binding/envelope design:
- `mizan.page-bindings.experimental.v2`: route mode ("current item").
  Same language-map envelope as v1 but the per-field reference is
  {mode:"route", module, source, field, on_missing} — no pinned item_key.
  Resolves against SourceContext.route_item; absent (previews, plain page
  URL) resolves None and the element follows on_missing. Route-selected
  reads require a recorded v4 consent for EVERY audience (v0-v3 wording
  never named URL-selected retrieval).
- `mizan.page-repeat.experimental.v2`: category card-repeat. Same column
  card template as v1 plus plan key category:"route"; expands through the
  new inventory collection source category_products backed by
  read_category_products (v4-recorded consent for every audience,
  category must be in the publication allowlist).
- text elements gain the description item-binding field (v4 consent
  field, 2000-char bound, fail-closed).
Depends on Phase 2 (done).

**Phase 4 — Website module (ERP side, user decisions 3-7).**
Rename frontstore -> Website; its tab manages orders, published products,
website attributes, and pages (non-UI records/behavior config only);
page edit opens standalone Studio in a NEW full browser tab with safe
auth/context handoff; cross-module bidirectional site data flow (e.g.
Help Desk) follows the same provider/consent pattern, each module keeping
its own data and logic. Rename/navigation can start in parallel with
Phase 2-3; the Studio launch handoff lands after Phase 3 contracts are
stable.

**Phase 5 — remaining Studio surface gaps.**
Per-device alignment/reorder/gap; arbitrary header sizing/colors; module
capability surfaces (cookies consent, notifications UI blocks, mobile
bottom panel — appearance in Studio, behavior config in the owning ERP
module); original source-asset workflow through the UI media library.

**Phase 6 — Wirya rebuild acceptance.**
Rebuild the full allwirya.live through the Studio UI only, using the
above capabilities; the remaining gap discoveries feed back into this
register.

Blocking user decisions: none. The coordinator's 17:37 proposal list
(SEO, domains, cookie policy settings, notification rules) is NOT
approved scope and waits for the user's explicit yes.

## Out of scope by user ruling
- Salon adapter: stays an honestly labeled placeholder. No salon adapter.
- Hosted test deploy (mizan-studio-feature-test.vercel.app): link sharing
  deferred by user until asked. Deploy is 2+ commits behind HEAD; re-verify
  before any share.
