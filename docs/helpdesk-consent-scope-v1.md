# Consent scope change: Help Desk website services — richer display fields (v1)

Status: **design for review; no implementation in this change set.** Main
authorized designing the wording in-branch (2026-11-25 ~20:50 EET: richer Help
Desk consent wording with source/field scopes designed under the existing
grant; page publication consent stays guarded). Same reversible pattern as
inventory v1/v2/v4 (docs/studio-consent-scope-v1.md,
docs/studio-consent-scope-v2.md, docs/studio-consent-scope-v4.md): no
auto-upgrade, no migration, older rows keep their recorded scope, re-saving
under older wording narrows back fail-closed.

## Why v0 does not cover this

The recorded v0 consent
(`mizan.helpdesk-website-services.experimental.v0`,
`helpdesk_website_publication_v0`) is **names only**. The provider docstring
states it as a contract: "no description, starting amount, currency, internal
notes or work data is ever a website field in this schema." A service card or
list that shows what a service costs or what it includes discloses fields the
owner never named:

1. **Description** (`HelpdeskOffering.description`, unbounded Text). Free-form
   business text; may contain internal wording the owner never reviewed for
   public display.
2. **Starting price** (`starting_amount` + `currency`). A price is a
   commercial commitment signal to a visitor; amount and currency only make
   sense together and must travel as one checked field, the same way
   inventory's price consent treats price.

Neither field is named by v0 wording, so v0 consent must not be read as
covering them.

## The change (design)

1. New schema `mizan.helpdesk-website-services.experimental.v1`. Payload
   gains two keys, both explicit booleans validated StrictBool at the writer:
   - `show_description` — the service description text.
   - `show_starting_price` — starting amount and currency, rendered together
     as a "starting from" price.
   v0 rows keep their exact 2-key shape (`schema`, `offerings`); a v1 row
   missing or mistyping either key is refused, same exact-key validation as
   v0.
2. Writer (`PUT /site/module-settings/helpdesk/publication`) stamps v1 only
   when the client acknowledges the v1 wording (`consent_version` guard, same
   mechanics as inventory: stale clients get 409, never a silent upgrade).
3. Reader acceptance:
   - v0 rows keep working exactly as recorded: names only.
   - `show_description` reads as True only on a v1 row; under any older
     schema the description column is never even selected.
   - `show_starting_price` reads as True only on a v1 row; under any older
     schema amount and currency are never selected.
   - Bounds, fail-closed like inventory: name ≤ 200 chars (unchanged),
     description ≤ 2000 chars, currency exactly 3 letters, amount rendered
     from the stored Numeric(14,2) with the non-negative constraint already
     enforced by the model. An over-bound value on a consented record fails
     the whole read closed (`SourceUnavailable`), never a partial render.
   - Collection CONTRACT for v1 adds `description` (plain_text, nullable,
     max 2000) and `starting_price` (formatted text, nullable) as optional
     fields present only when consented; `max_items` unchanged (24).
4. Audience semantics: v1 names the same surfaces v0 names (Studio-bound
   website collections/previews and the pages they serve under the page
   publication flow). It adds no new surface: richer fields ride the exact
   disclosure paths the owner already consented, with the new fields named.
   Page publication consent stays the guarded Studio flow (fresh approval per
   publish) and is unchanged by this wording.
5. Revocation: re-saving under v0 wording (or unchecking the boxes under v1
   wording) narrows back fail-closed; consented-but-inactive offerings keep
   dropping out as they do today.

## UI copy (bilingual, confirm dialog + section text)

English confirm: "Make these selected service names and checked display
fields available on your website? Checked fields: service description;
starting price. This does not enable booking or payment."

Arabic confirm: "نشر أسماء الخدمات المحددة والحقول المختارة على موقعك؟
الحقول المختارة: وصف الخدمة؛ السعر الابتدائي. هذا لا يفعّل الحجز أو الدفع."

The section text names each field with its source in Help Desk, mirroring the
inventory cards wording structure; unchecked fields state "names only."

## Proof and restore protocol (when implemented)

Same as inventory v1/v2/v4: offline suites with real models/statements and a
mocked session (no live DB claims), synthetic fixture offerings only, no real
business records consented by the agent. Live UI proof, when captured,
re-saves the workspace's own test consent and restores the exact prior
effective values afterward with edit_token deltas disclosed.

## Explicitly out of scope

- Implementation (this document is the design; writer/reader/UI changes land
  separately under the same reversible-work grant or an explicit go-ahead).
- Any page-publication consent change; the Studio publication flow stays
  guarded exactly as shipped.
- Booking, quoting, or checkout for services; display only.
- URL-selected service detail pages; if wanted later, that retrieval
  authority needs its own named wording, as inventory v4 did for products.
- Internal notes, ticket/work data, customer data: never website fields.
