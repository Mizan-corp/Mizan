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

G1. No search element. allwirya's header search is central; the builder has no
    search/store-search block. (Header editing also cannot inject one.)
G2. No header logo image (brand is text-only), no cart/account icons, no sticky
    header control.
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
    failed native-editor load entirely). Footer social icons remain unsupported.
    This was an implementation gap, not an authorization gate (2026-11-25, main).
    Repair-card checkmarks are covered by N2.
G6. No form/input element (CTA band's device-request input).
G7. Typography: one system font family site-wide; no heading size control, no font
    upload, no Arabic/Latin pairing (chrome UI states this itself). allwirya's Arabic
    display font cannot be reproduced.
G8. Color: no per-element color overrides. Partially addressed 2026-11-25 (N1
    shipped): theme gained a second surface pair (dark / dark-foreground) and
    sections/columns accept background=dark, so dark/light alternation is now
    reachable; accent-on-dark still routes through the single primary role.
G9. Store grids: product cards exist (consent-gated) but there is no "category card
    grid" or "service price list" preset; closest are pricing_cards/features presets.
G10. Footer is lines + flat links only; no multi-column footer, no social icons.

## Judgment

With current capabilities a normal user can reproduce the page's STRUCTURE and
Arabic RTL copy (hero, two cards, services list as pricing_cards, CTA band as
heading+text+button, footer links) at a recognizable but visually plainer level.
A faithful clone is blocked mainly by G3 (images), G1/G6 (search + input), G5
(icons), G7/G8 (typography/color depth), G4 (heading accent).

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
Blocked and NOT proposed until approved: image storage provisioning (G3), search and
form elements (G1/G6 - interactive surface needs its own consent/design pass),
font upload (G7). G5 icon set is an implementation gap, not approval-gated.
