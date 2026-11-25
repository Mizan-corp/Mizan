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
G4. No inline highlight inside headings (hero's blue span). Headings are plain
    escaped text; no rich spans.
G5. No icon system (service-card icons, checkmarks in the repair card, social icons
    in the footer).
G6. No form/input element (CTA band's device-request input).
G7. Typography: one system font family site-wide; no heading size control, no font
    upload, no Arabic/Latin pairing (chrome UI states this itself). allwirya's Arabic
    display font cannot be reproduced.
G8. Color: 5 theme roles only; no per-element color overrides, no second surface
    (allwirya alternates dark navy and light sections with blue accents; reachable
    only approximately via primary-as-surface).
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

N1. Section-level surface depth: allow the section background role list to include a
    second dark surface plus matching foreground, OR per-section explicit color
    override bounded to theme-safe values. Unlocks the dark/light alternation that
    defines allwirya's look. Reversible product UI work; no schema migration beyond
    the settings allowlist.
N2. Checkmark/feature list: a text variant or column preset rendering a bulleted
    check list (pure renderer + preset; no new data). Unblocks the repair card.
N3. Heading accent span: bounded inline mark support in heading text (one <mark>
    mapped to primary color), sanitized like text.html. Unblocks the hero accent.
N4. Category card preset (image + label + href grid) — degraded to art placeholders
    until G3 storage is approved.
Blocked and NOT proposed until approved: image storage provisioning (G3), search and
form elements (G1/G6 - interactive surface needs its own consent/design pass),
icon set (G5), font upload (G7).
