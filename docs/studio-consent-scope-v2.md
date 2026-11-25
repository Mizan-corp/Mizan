# Consent scope change: website display consent for individually bound elements (v2)

Status: **design for review; implementation authorized as reversible product
work** (main, 2026-11-25 03:43 EET). Main has not granted any actual v2 data
consent: no real business record may be consented under v2 by the agent;
proof uses isolated synthetic fixtures with effective-scope restore afterward.
v1 behavior is unchanged and a v1 consent row never unlocks scalar fields.

## Why the existing v1 consent does not cover this

The v1 consent wording (`mizan.inventory-website-cards.experimental.v1`,
same `inventory_website_cards_v0` setting key) names two surfaces only:
**product cards** and **repeating product lists** placed on pages, in
authenticated website previews. Binding a single page element (one heading,
one text, one image) directly to a consented product field is a **third
disclosure path**: different surface (per-element scalar binding), different
consumption (one record pinned to one element, not a card block or a repeated
list), same stored data. v1 wording does not name it, so v1 consent is not
read as covering it — exactly the same distinction main applied to v0->v1
(2026-11-25 02:02 EET) and reaffirmed for scalar (03:43 EET).

Current enforcement (pinned by `tests/test_scalar_binding_gate.py`):

- The scalar binding registry (`ProviderRegistry`) only accepts scalar source
  contracts; the inventory collection contract cannot register (ValueError at
  construction).
- An inventory scalar binding is refused `SourceUnavailable` and `resolve()`
  never calls the provider read.
- Typed money/media scalar targets are refused.

## Proposed change

1. New schema `mizan.inventory-website-cards.experimental.v2`, identical
   payload shape to v1 (`{schema, products, show_price, show_image,
   currency}`), same setting key, same writer route and permissions
   (site.manage + inventory, token-guarded). Only the consent **wording** and
   the recorded schema version change. The writer stamps v2 on every new
   save; the reader accepts v0 (cards only), v1 (cards + repeating lists) and
   v2 (cards + repeating lists + individually bound elements).
2. UI copy (`WebsiteCardSettings.tsx`, bilingual, exact wording drafted at
   implementation time and kept precise in both languages) names all three
   surfaces: individually bound elements, product cards, and repeating
   product lists; authenticated signed-in previews only; no publishing, no
   checkout.
3. No auto-upgrade and no migration: existing v1 rows keep v1 scope; nothing
   silently widens them. An owner who wants scalar binding re-saves under the
   v2 wording. Re-saving under older wording narrows scope back, fail-closed
   (same revocation semantics as v1: `docs/studio-consent-scope-v1.md`).
4. Scoped-item resolution: scalar reads resolve one selected record by id
   through the same consent intersection as cards (revoked products drop out
   per the user-approved 2026-11-24 semantics; malformed selections stay
   fail-closed), same typed money/media validation, same WorkspaceFile
   provenance check for images, same tenant/module/active-product guards.
   Optional columns are selected only after opt-in.
5. Binding declaration: a new versioned envelope
   (`mizan.page-bindings.experimental.v1`) carrying an explicit record
   identity (`item_key` from the owner's own current selection), bounded
   languages, on_missing hide/empty — no executable expressions, no embedded
   values, same bounded size/depth limits as v0. Targets: heading.text,
   text.html (escaped plain text fill; renderer escapes, never interprets),
   image.src (provenance-checked media only).

## Proof and restore protocol

Same as the v1 card-repeat protocol (docs/studio-website-acceptance.md):
synthetic fixture products only, real UI opt-in with captured bilingual
wording, pixel-verified preview proof, same-run restore to the exact prior
effective consent values with edit_token metadata deltas disclosed, no DB
cleanup, no real records.

## Explicitly out of scope

- No public/anonymous rendering of bound data (authenticated previews only).
- No checkout or publishing enablement.
- No image-slot claims while file storage is unconfigured on the test host
  (see deploy/studio-test/README.md — uploads refused by design without
  BLOB_READ_WRITE_TOKEN; storage provisioning is unapproved and its
  account-specific terms are unverified).
- No stock, cost, wholesale, barcode, internal-location or customer fields —
  never display fields.
