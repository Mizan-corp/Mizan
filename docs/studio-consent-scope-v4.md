# Consent scope change: category linkage and URL-selected product detail (v4)

Status: **design for review; implementation authorized as reversible product
work** (main, 2026-11-25 ~17:37 EET: "extend explicit UI publication consent
accurately for category-product linkage/current-record retrieval, keep scoped
published records only"). Grounded in the user's own requests (2026-11-25
17:30/17:32 EET): categories implemented from the Inventory module with all
content managed there, and one Studio-authored product template applied to
every product with the product ID determining its URL. Same reversible
pattern as v1 (docs/studio-consent-scope-v1.md) and v2
(docs/studio-consent-scope-v2.md): no auto-upgrade, no migration, older rows
keep their recorded scope, re-saving under older wording narrows back
fail-closed.

## Why v0-v3 do not cover this

The recorded wordings cover product names (publication allowlist), and the
checked display fields (price, image) on cards (v0), repeating lists (v1),
individually bound elements (v2), and public pages (v3). Two disclosure
paths in the user's requested architecture are named by none of them:

1. **Category membership linkage.** A category page shows the consented
   products that BELONG to a published category. Even when each rendered
   field was already consented, the page itself discloses a new fact: which
   category each shown product belongs to (Product.subcategory_id ->
   Subcategory.category_id). v0-v3 never name category membership.
2. **URL-selected current-record retrieval.** A product-detail template is
   authored ONCE and renders the product whose ID is in the URL. v2/v3
   element consent covers an element pinned to one specific record the owner
   picked (`item_key` recorded in the page); a URL-selected read resolves
   ANY record the visitor names, bounded only by the consented set. That is
   a different retrieval authority and needs to be named.
3. **Description as a display field.** Product detail needs the description
   the user manages in Inventory. Description is a new display field, never
   named by any wording (v0-v3 name only price and image as optional
   fields). It ships as its own explicit checkbox (`show_description`),
   same pattern as show_price/show_image, bounded at 2000 characters
   (over-bound values fail closed, same as the 200-char name bound).

## The change

1. New schema `mizan.inventory-website-cards.experimental.v4`. Payload gains
   one key: `show_description` (explicit bool, StrictBool at the writer).
   v0-v3 rows keep their exact 5-key shape; a v4 row missing or
   mistyping the key is refused.
2. Writer (`PUT /site/module-settings/inventory/cards`) stamps v4 only when
   the client acknowledges the v4 wording (`consent_version` guard,
   unchanged mechanics: stale clients get 409, never a silent upgrade).
3. Reader acceptance:
   - Cards/lists/elements under v1/v2/v3 wording keep working exactly as
     recorded (stored_policy accepts v4 as well).
   - `show_description` reads as True only on a v4 row. Under any older
     schema the description column is never even selected.
   - Category linkage (`read_category_products`) requires a recorded v4
     row, for previews AND public reads: linkage was first named in v4.
     The category itself must be in the publication allowlist, and only
     consented, active products in it are returned (revocation drops them
     out, user-approved 2026-11-24 semantics).
   - URL-selected retrieval resolves through the same gate: the requested
     ID must be in the consented product set, active, tenant- and
     module-scoped; malformed IDs fail closed. Public audience still
     requires wording that names public pages (v3+, including v4).
4. UI copy (WebsiteCardSettings, bilingual Arabic + English, confirm dialog
   and section text) names all surfaces precisely: cards, repeating lists,
   individually bound elements, URL-selected product detail pages, and
   category pages that reveal which selected products belong to a selected
   category; the description checkbox names the description field
   explicitly.

## Proof and restore protocol

Same as v1/v2: offline suites with real models/statements and a mocked
session (no live DB claims), synthetic fixture products only, no real
business records consented by the agent. Live UI proof, when captured,
re-saves the workspace's own test consent and restores the exact prior
effective values afterward with edit_token deltas disclosed.

## Explicitly out of scope

- The route/template wiring that CONSUMES these primitives (product/{id}
  route shape, "current item" binding mode, category destinations in menus)
  is Phase 3; this change ships only the consent foundation and the gated
  read primitives with tests.
- No stock, cost, wholesale, barcode, supplier, internal-location or
  customer fields — never display fields.
- No checkout enablement, no cart, no orders.
- Description rendering is escaped plain text fill only; the renderer never
  interprets markup.
