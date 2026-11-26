# Visitor runtime V3: multi-page site milestone (synthetic scope)

Branch: `feat/studio-render-parity`. Deployment verified: `mizan-studio-feature-test.vercel.app` (deploy 2huxdy8ge). All state below is on the isolated test workspace only; no real business data anywhere in the path.

## What an ordinary user can now do, end to end, without code

1. Open `/studio/`. With more than one page, a Pages switcher appears ("Choose a page") instead of a dead-end block.
2. Switch between editable pages, or choose "+ New page". A new page asks for a deliberate page address (lowercase letters, numbers, hyphens; validated client-side; fixed after first save).
3. Edit, Save, Publish, Make public per page. Each public page is served at `/site/studio/<page-slug>` on the configured host.
4. Header/footer links (site-wide settings) with root-relative destinations like `/welcome` resolve publicly: the renderer rebases them under the mounted site path (`/site/{slug}`). The same rebase applies to button links inside page content. Anchors (`#x`), protocol-relative and absolute URLs are never rebased.

## Verified behaviors

- Two UI-authored pages live anonymously: `/site/studio/studio-hello-2026` and `/site/studio/studio-second-page`, plus `/site/studio/welcome` (kit-built; refused by the simple editor without conversion).
- Save-without-Publish preserves the public snapshot: a saved draft edit did not appear in visitor HTML until Publish.
- Edit-after-publish propagates on Publish; the activation theme snapshot refreshes at publish time for the edited shared settings (header brand). Page `<title>`/og:title come from the page's own title field; footer lines are a separate field.
- Unsaved-change guard (beforeunload) engages on page switching with unsaved edits.
- Unknown page path: 404.

## Authorization evidence (public-access and site APIs)

- Unauthenticated: 401.
- Authenticated without `site.manage` (fixture cashier user): 403 on pages list, public-access GET and PUT. Distinct from 401.
- Unknown or other-tenant page id: generic 404 (no existence oracle).
- Hostile body (custom host/slug/`allow_connected_data:true`): accepted fields are ignored; activation stays pinned to the configured host and fixed site slug, `allow_connected_data` stays FALSE.
- Tree containing data-binding/provider nodes: 409 "Pages that read business data cannot be made public in synthetic scope" (both at publish and at public-access time).
- Custom host can never activate: the host comes only from trusted server config (`PUBLIC_SITE_HOST`).

## Implementation

- `render.py`: `_site_link` + `link_base` threaded through `render_document` → `_theme_chrome`/`_theme_links` and `render_page` → button nodes.
- `public_pages.py`: passes `link_base=/site/{slug}`.
- `main.tsx`: Pages switcher (also visible in the multi-page blocked state) and the new-page Page address field; `sitePages.ts`: `createPayload(project, slugOverride?)` with slug validation.
- Tests: shared suite 95 passed (3 theme-link rebase + 1 content-button rebase in `test_public_access.py`); studio suite 123 passed.

## Known gaps / next increments

- The simple Studio's page switcher lists pages it cannot edit (kit-built/native trees); those load as protected read-only, which is correct but not signposted in the list.
- Page title (`<title>`/og) and slug are set at creation only; no rename flow in the simple Studio (NativeStudio can edit titles of unpublished drafts).
- `POST /users/{id}/reset-password` returned 500 on this deployment (fixture cashier user; generic error). Suspected audit-insert issue on model-provisioned databases. Found during fixture cleanup; the user was retired via the supported DELETE instead. Not investigated further yet.
- Header Search/Bag remain static fixture text; no forms, search, cart, accounts or checkout in synthetic scope.
