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
13. **Import-path correctness (resolved 2026-11-25).** The venv
    (/tmp/mizan-venv) carries an editable install whose meta-path finder
    always resolved `app` to /tmp/mizan, a stale non-git snapshot, silently
    shadowing the working branch in every plain import. Fixed durably: the
    finder MAPPING now points at /tmp/mizan-push/shared/backend/app.
    Verified loaded paths: app.framework.manifest and the inventory
    storefront modules resolve to /tmp/mizan-push/... files. All backend
    suites were re-run after the fix and pass against the intended code;
    any passing evidence from before the fix is superseded by that
    revalidation. Live uvicorn servers (system 8000, website 8001) run
    with cwd inside /tmp/mizan-push and pick up current code on restart.
14. **Website-backend public_pages tests** — RESOLVED 2026-11-25. Root cause
    was Phase 3 signature drift, not a pre-existing defect: the request mock
    lacked query_params and three _render_public test doubles predated the
    ?q/?lang/route-item kwargs. Mocks updated; the file is green (23 tests).
    Also fixed the same day: the connected-data approval dry-run and the
    visitor render path called resolve_tree/resolve_composition without the
    item resolver, so pages with element item bindings always failed approval
    ("Element binding source is unavailable"); both paths now pass
    item_resolver(db), pinned by a regression test in
    test_connected_data_access.py.

15. **Card repeat row limit** — RESOLVED 2026-11-25. A columns block holds
    1..6 columns, but the card repeat wrote limit 8 and expansion produced a
    single over-full row, so any category/collection with >6 items 503'd at
    render ("Expanded page is not a valid bounded native tree"). Expansion
    now splits clones into sibling rows of at most 6, cloned from the
    template's row with fresh derived identities. Regression:
    test_collection_card_repeats.py::test_more_than_six_cards_split_into_valid_rows.
16. **Approval dry-run does not exercise route-parameterized reads** — OPEN.
    set_connected_data_access resolves the published tree with no route item,
    so v2 route-mode sources (route item, route category) are validated for
    plan shape and consent gates only; the real per-record read first runs at
    visitor request time (this is how #15 reached the visitor). Visitor-pair
    E2E is the required evidence for route-mode pages until the dry-run gains
    a probe read; any loosening of the consent gates to shortcut this is
    refused by design.

17. **Publish/enable concurrency test against a real database** — OPEN
    (visual/security reviewer closeout, 2026-11-25; their F3). The
    publish/enable lock is currently covered by mocked-session tests only;
    a real-DB concurrency pass (two simultaneous publish/enable requests,
    one must conflict) is still owed.
18. **Style panel minors** — OPEN (same closeout). Lavender literal
    rgb(145,131,158) bypasses the token scale; three invisible debug nodes
    sit in the Style panel DOM. Cosmetic only, fix in a cleanup pass.
19. **Legacy /studio/ route disposition** — RESOLVED 2026-11-25 in
    feat/studio-render-parity by grounding the production deploy layout
    (deploy/studio-test): package.py copies studio-preview.html to
    /static/index.html — the server-backed Studio (PreviewSession) IS the
    deployment root entry — while deploy.sh:53 builds the older Northline
    prototype (main.tsx, studio.html) into /studio/. The prototype marks
    backend pages read-only (no save/publish) unless an explicit ?page=
    link opens it, and even then keeps browser-copy-only editing. The ERP
    launcher therefore targets /studio-preview.html (same-origin, session
    cookie carries the sign-in); /studio/* stays served untouched for
    prior-route compatibility but nothing launches it. Verified live on
    the same-origin harness: ERP login -> /website -> launcher click ->
    /studio-preview.html loads the full Studio home with the workspace's
    real pages and no second login.

Reconciled from the same closeout (no gap item needed): the reviewer left
the Home "كل الصفحات ←" / library link click paths inconclusive. Verified
in source 2026-11-25: "كل الصفحات ←" is a search-reset button rendered only
while a query is active (PreviewSession.tsx, clears the filter — correct by
design); "المكتبة الكاملة" appears only in the concept mockups, not in the
implementation (the implemented entry is "اتفرّج على القوالب", an in-page
scroll to the templates section). Home search reset and Library minis
passed the reviewer's final boundary.

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

**Phase 4 — Website module (ERP side, user decisions 3-7).** IN PROGRESS.
Rename frontstore -> Website; its tab manages orders, published products,
website attributes, and pages (non-UI records/behavior config only);
page edit opens standalone Studio in a NEW full browser tab with safe
auth/context handoff; cross-module bidirectional site data flow (e.g.
Help Desk) follows the same provider/consent pattern, each module keeping
its own data and logic.

DONE 2026-11-25 (first slice): ERP route /website (Guard site.manage) with
the pages list (status, slug, archived filtered) and the same reviewed
module/consent settings components the Studio Data panel mounts (no
duplicated catalog; Inventory stays source of truth); every design edit
opens the standalone Studio in a NEW full tab via
window.open('/studio-preview.html?page=<id>', '_blank', 'noopener,noreferrer')
(the deployment's root-entry bundle; /studio/ is the older read-only
prototype, see item 19) — the session cookie carries
the sign-in, the page id rides in the query string, never a token. App
launcher entry renamed storefront -> الموقع/Website (id "site", the
platform module that owns the site API), fixing the previously dead
/storefront link. vitest: WebsitePage 6/6; full frontend suite unchanged
(303 passed, 1 skipped, 1 pre-existing treerender fail).
PENDING: orders surface (which orders belong here vs the legacy commerce
storefront module is unresolved — the old StorefrontAdminPage/backend stay
untouched); cross-module (Help Desk) provider/consent surfaces; live ERP
E2E of the new tab (the sandbox runs no system-app server; the endpoints
are the already live-proven /site/pages and module-settings routes);
legacy /studio/ route disposition (item 19).

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
