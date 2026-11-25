# Consent scope change: website display consent for product lists/repeats (v1) — FOR REVIEW

Status: **prepared, not implemented in any UI. Nothing writes a v1 policy today.**
This is the concrete consent-scope change requested before any collection/repeat
provider may expose price/image.

## Why the existing consent does not cover this

The current card consent (`mizan.inventory-website-cards.experimental.v0`,
`inventory_website_cards_v0`) was saved under wording that names **cards** and
**authenticated website previews** only:

- Confirm dialog (EN): "Make these selected product names and checked display
  fields available in authenticated website previews? … This does not publish or
  enable checkout."
- Legend (AR): "المخزون · موافقة كروت المنتجات" (product cards consent).

A collection/repeat provider rendering price/image inside repeating lists on
bound pages is a **new disclosure path**: different surface (list/repeat
projection, not the cards block), different consumption (template-bound
repetition), same stored data. The v0 wording does not name it, so v0 consent is
not read as covering it (`cards.display_consent()` returns consent only for the
v1 schema). Owners who already consented to cards must re-consent under the new
wording. No data migration rewrites v0 rows; re-saving under v0 wording (the
current UI) effectively revokes list display consent.

## Proposed change

1. New schema `mizan.inventory-website-cards.experimental.v1`, identical payload
   shape to v0 (`{schema, products, show_price, show_image, currency}`), same
   `inventory_website_cards_v0` setting key, same settings writer route and
   permissions (site.manage + inventory, token-guarded). Only the consent
   **wording** and the recorded schema version change.
2. The card settings UI (`WebsiteCardSettings.tsx`) gains updated copy
   covering both surfaces. Proposed wording:

   EN confirm dialog:
   > Make these selected product names and checked display fields available in
   > authenticated website previews, including product cards and repeating
   > product lists you place on pages? … This does not publish or enable
   > checkout.

   AR legend (draft, owner to confirm):
   > المخزون · موافقة عرض المنتجات على الموقع (كروت وقوائم)

   AR confirm (draft, owner to confirm):
   > الموافقة هتخلي أسماء المنتجات المختارة والحقول المحددة متاحة في معاينات
   > الموقع المقفولة بحسابك، سواء في كروت المنتجات أو القوائم المتكررة اللي
   > بتحطها على الصفحات. ده مش نشر ومش بيفعل الدفع.

3. Behavior on save: the writer stamps `schema: ...v1`. v0 rows remain valid
   for **cards only** (unchanged behavior); list/repeat reads require v1.
4. Revocation: unchecking fields/products or re-saving reduces scope exactly as
   today; replacing a v1 row with a v0 row (only possible via older UI builds)
   silently narrows consent back to cards, fail-closed for lists.

## What is already in place (prep, no behavior change)

- Collection contracts may declare typed fields with exact specs
  (`{type: money|media, semantic: display_money|display_media, nullable}`) —
  `collection_problems` validates them; `CollectionRuntime.items()` validates
  values with `check_money`/`check_media` (tenant-scoped).
- Heading collection expansion refuses non-text plan fields (plain text only).
- Inventory `products` collection contract declares optional `price`/`image`;
  `read()` fills them **only** from a v1 consent, selecting the optional columns
  only after opt-in, with the same WorkspaceFile provenance check as cards.
- Tests: `tests/test_collection_typed_fields.py` (16 tests: contract shape,
  typed validation, heading refusal, v0-vs-v1 gating, provenance fail-closed,
  revocation by v0 rewrite, cross-tenant refusal, end-to-end through the
  collection runtime). Full offline suite: 119 tests, 3 pre-existing
  env-dependent loader errors unchanged.

## Not in scope (unchanged)

- Public connected-data rendering stays blocked
  (`site_activation.allow_connected_data=false`).
- No legacy/foreign image URLs; tenant-scoped blob paths with provenance only.
- No cost/supplier fields ever; money stays two-decimal display values with
  explicit currency, no FX or scale claims.
- No new external requests.
