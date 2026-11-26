# allwirya.live UI-only recreation: capability map and verified gaps

Date: 2026-11-25. Host: mizan-studio-feature-test.vercel.app (workspace studio-test).
Success criterion (user, 2025-11-23): "Make a clone of allwirya.live without typing a
single line of code as a normal user." This document records what the native builder
can already do, what it verifiably cannot, and the next unblocked implementation.

## Reference inventory (allwirya.live home, captured 2026-11-25 ~04:41 EET)

Top to bottom (RTL, Arabic):

1. Sticky store header: logo image, search box, cart/wishlist/account icons, language
   switch, category nav (كل المنتجات، لابتوبات، قطع ومكونات، وحدات تخزين، شاشات،
   إكسسوارات، شبكات، الخدمات، تتبع جهازك، الكتب), primary CTA "احجز صيانة".
2. Hero: badge pill, large heading with a blue-highlighted span, subtext.
3. Two-offer row: white card (أجهزة وقطع + product thumbnails + price note + 2 buttons),
   dark-blue card (صيانة واستعادة بيانات + checkmark list + 2 buttons), center photo.
4. Services section: oversized section heading + service cards with icons and prices
   (من 80 ج.م / 100 ج.م / 50 ج.م) + note row.
5. Store section (light background): heading + "تسوّق حسب القسم" category image cards
   + product grid + "كل المتجر" links.
6. CTA band (dark): "اطلب أي جهاز أو قطعة ونوفرها لك" + free-text input + WhatsApp
   button (green) + reassurance line.
7. Installation band (dark card): "اشترِ القطعة، ونركّبها لك" + 2 buttons.
8. Books section, repair-tracking section (mid page, not re-captured this run).
9. Footer: 5 link columns (المتجر، السياسات، وریا، النشر، طرق الدفع), payment note,
   delivery areas, logo + social icons, copyright line.

Reference screenshots: cloud-browser-20261125-024139 (hero), -024124 (services),
-024129 (CTA band), -024133 (footer) — saved under /downloads on the proof agent.

## What the builder already covers (verified in code + live)

- Page templates and 19 block presets, insert without code; 4-page Tech store set
  (created as drafts: wirya-recreate-home/-products/-services/-contact).
- Element set: section / columns (1-6, gap, stack, reverse) / column / heading
  (levels, align) / text (body, eyebrow, note) / image / button (3 styles).
- Per-section and per-column background from theme roles (background/card/primary),
  max-width, padding, visibility, entrance motion.
- RTL rendering for Arabic content (dir=rtl at render), bilingual per-element content.
- Site chrome editor: header brand text, up to 8 nav links + 4 action links with a
  page-address picker, footer lines + links, presets; site design: 5 color roles,
  one system font family, corner radius, staged preview before site-wide save.
- Product cards and repeating lists with v1 consent; individually bound elements
  (one field of one consented product) with v2 consent; fail-closed revocation hide.
- Preview is authenticated-only; publish stays a deliberate separate action.

## Verified gaps (block a faithful clone today)

G1. PARTIALLY RESOLVED 2026-11-26: catalog search shipped as header chrome
    (theme.header.search_enabled/search_target/search_placeholder, editable in
    Style > Header, persisted per activation snapshot) plus a plain GET form and
    `?q=` filtering on collection repeat pages. The filter matches only the
    disclosed heading field of consented, published, in-allowlist products;
    unconsented queries render an escaped bilingual no-results notice; the
    current page language is preserved through submission via a hidden lang
    input. Live-verified on the visitor route (form renders, q filters to the
    matching laptop only, unconsented query leaks nothing, HTML injection is
    escaped, ?lang=en survives the submit). Remaining: an in-page "search this
    page" filter block (needs the first visitor-side JS - platform decision)
    and a GET-form static-content site search (needs an endpoint decision) from
    docs/studio-search-form-design.md are still not implemented.
G2. PARTIALLY RESOLVED 2026-11-25: header logo image by URL shipped (theme.header.logo,
    safe /path or https URL, rendered as an escaped img in both renderers, editable in
    Style > Header as "Logo URL (optional)"). Header icon links shipped 2026-11-26
    (c0f41f08): a bounded icon row (whatsapp/cart/heart/user/phone/globe, up to 6,
    safe links only) editable in Style > Header and rendered in both renderers;
    these are visual links, not wired cart/account functions. Remaining: no
    functional cart/account wiring, no sticky header control, no upload-based logo (G3).
G3. Image upload/storage not connected on the test host (no BLOB_READ_WRITE_TOKEN;
    provisioning not approved). Blocks hero photo, category cards, product photos.
    Image elements accept URLs; art placeholders exist (sculpture/sculpture_alt).
G4. Partially addressed 2026-11-25 (N3 shipped): headings support one bounded
    accent span via literal <mark>..</mark> pairs mapped to the primary color
    (all other markup still escapes; editor offers an Accent toggle on the
    heading selection). Arbitrary rich spans remain unsupported.
G5. Partially addressed 2026-11-25 (icon_list shipped): the icon_list block now
    renders a bounded inline-SVG set (20 icons, no icon font, no network fetch)
    in both renderers, unknown stored names fall back to a dot, and the native
    editor exposes it end to end: an Icon list Insert preset, per-item icon
    picker + label editing, and tree validation (previously icon_list trees
    failed native-editor load entirely). Footer social icons shipped 2026-11-26
    (ad901c45): theme.footer.socials, up to 6 entries over a named set
    (whatsapp/facebook/instagram/x/youtube/linkedin), sanitized label + safe link
    (/, #, https://) per entry, editable in Style > Footer, rendered as
    mz-footer-socials with accessible labels in both renderers; live-verified
    UI-authored save > publish > visitor SSR (RTL desktop + mobile).
    This was an implementation gap, not an authorization gate (2026-11-25, main).
    Repair-card checkmarks are covered by N2.
G6. MOSTLY RESOLVED 2026-11-25 (36c0c30c): native form block shipped - title,
    always-on email + message fields, optional name/phone toggles, editable
    labels/submit/success text, live visitor POST with Website inbox storage and
    admin read. This covers the FUNCTION of the CTA band's device-request input
    (a visitor submits free text and it lands in the Website inbox). It does NOT
    reproduce the original layout: an inline single-line input inside a colored
    CTA band row. The form block is a vertical form section; email is always
    required, so a message-only composition is not possible. Inline-band input
    remains unsupported.
G7. Typography: one system font family site-wide. Heading size control shipped
    (451132c2): headings accept size auto/s/m/l rendered as bounded font-size
    clamps (mz-size-*) in both renderers. Remaining: no font upload, no
    Arabic/Latin pairing (chrome UI states this itself). allwirya's Arabic
    display font cannot be reproduced.
G8. Color: no per-element color overrides. Partially addressed 2026-11-25 (N1
    shipped): theme gained a second surface pair (dark / dark-foreground) and
    sections/columns accept background=dark, so dark/light alternation is now
    reachable; accent-on-dark still routes through the single primary role.
G9. RESOLVED 2026-11-26: doc drift - the "Category cards" preset already exists
    (eabbc70e, Catalog category: artwork + name + text + browse link per card,
    editable in Studio) and covers the category card grid; the service price list
    is composable with the pricing_cards preset (Arabic preset names for
    category_cards/icon_list/check_list/contact_form added in the same change -
    Arabic UI previously fell back to English for those four).
G10. RESOLVED 2026-11-26: multi-column footer shipped (theme.footer.groups: up to
    4 titled link groups, 6 links each, rendered as mz-footer-groups columns in
    both renderers, editable in Style > Footer as "Footer link groups"). Footer
    social icons shipped 2026-11-26 (ad901c45, see G5).

## Judgment

With current capabilities a normal user can reproduce the page's STRUCTURE and
Arabic RTL copy (hero, two cards, services list as pricing_cards, CTA band as
heading+text+button, footer links) at a recognizable but visually plainer level.
A faithful clone is blocked mainly by G3 (images), G6 remainder (inline-band
input layout), G7 remainder (font upload/pairing), G8 (color depth), G4
(heading accent). G1 catalog
search shipped 2026-11-26 (header chrome + `?q=` filtering); only the in-page
filter and static-content site search variants remain open there.

## Next useful unblocked implementation (proposal, in priority order)

N1. SHIPPED 2026-11-25 (feat/studio-render-parity): section/column background role
    "dark" plus dark / dark-foreground theme tokens (renderer, SDK manifest,
    settings validation, editor style tab and format panel, both preview CSS
    copies). Per-section explicit color override remains open.
N2. SHIPPED 2026-11-25 (feat/studio-render-parity): text block variant
    check_list (both renderers + registry + Format panel) plus a "Check list"
    Insert preset. Bullets render with a primary-colored check mark, no icon
    system and no new data. Unblocks the repair card.
N3. SHIPPED 2026-11-25 (feat/studio-render-parity): literal <mark>..</mark>
    pairs in heading text render as primary-colored accent spans in both
    renderers (attributes, nesting and all other markup escape); the heading
    editor has an Accent toggle on the current selection.
N4. Category card preset (image + label + href grid) — degraded to art placeholders
    until G3 storage is approved.
N5. SHIPPED 2026-11-25 (feat/studio-render-parity): kit columns keep mobile padding
    's' by default (was 'none' for non-card columns, crushing text edge-to-edge on
    phones); affects future kit applications.
N6. SHIPPED 2026-11-25 (feat/studio-render-parity): image src and button href fall
    back across languages only when unset in the active language; explicit empty
    stays blank, labels never fall back, unlabeled buttons stay hidden. Both
    renderers share the rule (render.py _content_ref, treerender contentRef).
N7. SHIPPED 2026-11-25 (feat/studio-render-parity): content editing language
    persists across ALL in-app page switches; page titles gate only the first-load
    default (an English-only title no longer resets an Arabic editing session).
N8. SHIPPED 2026-11-25 (feat/studio-render-parity, commit b8c869f): header logo via
    URL + footer link groups in shared site chrome. Backend check_settings validates
    and preserves both losslessly (logo: trimmed, <=300 chars, /path or https://,
    page_url-checked; groups: <=4 titled groups, <=6 links each, same link rules as
    flat links); render.py emits escaped img and mz-footer-groups columns; frontend
    mirrors in treerender ThemeHeader/ThemeFooter, chromeProblems, the classic
    Project chrome round-trip (model/pagetree/sitePages) and the Style panel editor
    (Logo URL field, add/remove group, per-link label+URL rows). Live-verified on
    the test deployment through the no-code flow: logo /studio-assets/tech-laptop.svg
    and one Arabic footer group (الشركة > من نحن) saved via Style panel and confirmed
    in GET /api/site/settings plus canvas pixels. Draft page titles are now bilingual
    on all four recreation drafts (Home الرئيسية, Contact تواصل معنا).
N8 follow-ups 2026-11-25 (commits 7f6f8aa, +button rhythm): footer links now inherit
    color and drop underline in both renderers (were UA default blue); button blocks
    carry the shared 24px bottom margin like headings/text (stacked CTAs no longer
    touch - root-caused, no draft mutation needed). Verified live on Arabic content
    with English chrome: 24px CTA gap, inherited link color, dir=rtl, zero footer
    overflow at the 390px mobile frame.
Draft data fixes 2026-11-25: selected-product card recomposed through editor
controls only (1-col row -> 2 columns via Insert, heading+price moved with the
Move drag handle, image width full) - balanced text-left/image-right on desktop,
stacked on mobile, saved and API-verified.
Blocked and NOT proposed until approved: image storage provisioning (G3), the
remaining search variants (G1 remainder - design researched in
docs/studio-search-form-design.md; the numbered consent points there gate any
live enabling), font upload (G7). Form elements shipped 2026-11-25 (36c0c30c,
see G6); the G5 icon set shipped 2026-11-25/26 (icon_list + header icon row +
footer socials).

## Hosted evidence, 2026-11-26 (isolated test host)

- G6 inline request band: resolved. Authored in the Studio UI (name off, email
  off, inline layout), published, and a visitor submission reached the Website
  inbox as a message-only payload.
- Category template (`/site/studio/<page>/c/<category-id>`): authored in the
  Studio UI with "Category products from the page link", published with
  per-page approval of `inventory.category_products`. A visitor sees only the
  products of that category; an unknown id returns 404.
- Product detail template (`/site/studio/<page>/p/<product-id>`): heading and
  text elements bound to "Product from the page link" (name, price,
  description). Revoking public data made the URL return 404; re-approving
  restored it. A bug hid the field selector for URL-bound elements; fixed in
  aa6f8c4b.
- Still open: a live product grid on the Products page, category cards linking
  to `/c/<id>`, product images (test products have none), and the Settings
  audit.
- Test data only: six test products and three categories on the test tenant.
- Products page (2026-11-26): the live grid is bound to `inventory.products`
  in both languages and the category cards link to `/c/<id>` through buttons.
  Finding: a static sibling column in the same row as a repeat column made the
  publish approval fail with a generic "data source not exposable" message.
  Removing the sibling fixed it. The refusal message should name the cause.

## Repeated cards as a multi-column grid (2026-11-26)

- No new code was needed. The row that holds a repeat column already has a
  "columns" setting (1 to 6). Setting it to 3 on the row makes the repeated
  copies flow into a three-column grid for visitors (mobile still stacks).
  The row is selected on the canvas; it is not listed in Layers.
- Adding a child to a repeat column (for example an image) is refused while a
  repeat is attached ("Unsupported repeat template", slots are fixed). The UI
  path is: detach the repeat in each content language, add the element, then
  attach `inventory.products` again in each language.
- Evidence: visitor EN screenshots of the Products page on the test host show
  six product cards with name, price and uploaded image in three columns.
- Regression test: `test_declared_column_count_lays_out_expanded_repeat_copies_as_a_grid`
  in `shared/backend/tests/test_public_access.py`.
- Open usability gaps: the row cannot be picked from Layers, and the refusal
  message for editing a repeat column does not say to detach the repeat first.
