# Visitor runtime V2 milestone: Studio-to-public round trip through the UI only

Status: verified live on the isolated test host
(https://mizan-studio-feature-test.vercel.app), branch `feat/studio-render-parity`.
Scope remains synthetic only: no business data, no accounts, no cart, no checkout,
no tracking. Nothing on production business systems changed.

## What an ordinary user can now do, with no code and no console steps

1. Sign into the workspace and open the hosted Studio at `/studio/`.
2. Start a new page ("Start a new page instead" when no editable page is selected).
3. Edit brand, headings, descriptions, palette, typeface, header/footer chrome in
   the inspector; the live local preview updates.
4. "Save to workspace" creates/updates the server-side page and site settings.
   The notice now names the workspace backend correctly in hosted mode
   (`saveResultNotice(saved, current, hosted)`).
5. "Publish" marks the saved snapshot published.
6. "Make public" (new) writes the public activation through the authenticated
   API: `PUT /api/site/pages/{id}/public-access` with `{enabled: true}`.
   The notice shows the public URL; "Make private" retracts it. Both were
   exercised live: anonymous GET flipped 200 -> 404 -> 200 exactly on the UI
   actions, with the welcome page and unknown pages unaffected.
7. Visitors reach the page anonymously at
   `https://<host>/site/studio/<page-slug>`.

## The scoped activation API (the V1 manual step, replaced)

`system/core/backend/app/platform/site/service.py` grew `get_public_access` /
`set_public_access`, exposed on the existing site.manage-gated pages router
(`GET`/`PUT /site/pages/{page_id}/public-access`). Hard limits, enforced in the
statement and service, not by convention:

- host is the deployment's own `PUBLIC_SITE_HOST` from server config (never a
  client header); unconfigured host -> 409.
- slug is the fixed synthetic test-site slug `studio`.
- `allow_connected_data` is pinned `false` inside the INSERT itself; connected
  business data exposure stays a manual, separately reviewed operation.
- only published pages can be made reachable (409 otherwise); making private is
  always allowed.
- the activation theme snapshots the workspace's saved site settings at write
  time, so the public header/colors match what the Studio settings describe;
  the tenant's shared settings are still never read at request time.

DB fix that this surfaced: v112 created `site_activation` after the
`ALL TABLES` grant to the request role `mizan_app`, so UI-driven writes failed
with permission denied. Migration `v113_site_activation_app_grants` grants
SELECT/INSERT/UPDATE/DELETE on it to `mizan_app` (forced-RLS tenant policy still
governs every row), and the same grant was applied to the live isolated
database directly.

## Renderer: real responsive behavior

The visitor route renders each page once with desktop settings, so narrow
viewports previously kept multi-column grids and full gutters (the 390px
squeeze). `_BASE_CSS` now carries real media queries instead of relying on
device-rendered classes:

- `<=1024px`: 4-6 column grids collapse to 2 columns.
- `<=768px`: all multi-column grids stack to one column, gutters 24->16px,
  section padding 32->24/16px, fractional width utilities go full width.

Verified with pixels at 390px, 820px and desktop for the Studio-authored page
and at 390px for the welcome page.

## CTA and preview parity

- Hero/section buttons previously emitted `href="#preview"`, an anchor that
  only existed in the editor. `toPageTree` now points each CTA at the next
  section's node anchor, or `#n_root01` from the last section; every target is
  an id the same tree renders, so the button behaves identically in the local
  preview and on the public page. `fromPageTree` accepts the legacy `#preview`
  constant (upgraded on the next save) and refuses any other custom
  destination, keeping its fail-closed contract.
- The local editor preview is labeled "LIVE LOCAL PREVIEW" with a note that a
  public page's header/footer come from the site's saved public settings; the
  shared-renderer snapshot is labeled as such. Since the activation theme is
  the saved settings snapshot, the public chrome now matches the Studio
  settings one-to-one.

## Verification evidence

- Studio suite: 26 files, 123 passed, 1 skipped (backend contract check).
- Shared backend suite: 87 passed (9 new: public-access service guards +
  responsive CSS). Website suite public_pages: 23 passed.
- Live UI journey (cloud browser, fixture owner, isolated workspace): reload
  page from backend, Save, Publish, Make public -> anonymous 200 with the
  exact typed content, Make private -> 404, Make public -> 200.
- Negatives: unknown page 404; unpublished draft 404; welcome page served
  throughout.
- Pixels: visitor 390/820/desktop for the Studio page, 390 for welcome, and
  the Studio UI showing the Make private control and public URL.

## Honest limits that remain

- Public access is per page on the deployment's own host only; no custom
  domains, no connected data, no forms/search/cart/accounts.
- The editor remains intentionally narrow: it refuses trees it cannot
  represent (fail closed) and offers the non-destructive new-page route
  instead.
- The activation theme is a snapshot from activation time; later settings
  edits apply to the public page on the next Make public / publish cycle.
- Header actions such as Search/Bag in the sample chrome are static labels in
  synthetic scope; they have no behavior behind them.
