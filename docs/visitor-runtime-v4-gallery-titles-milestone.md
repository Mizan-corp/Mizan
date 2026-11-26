# Visitor runtime V4 milestone: gallery sections, page titles, signposting, reset-password fix

Scope: `feat/studio-render-parity` only. Isolated deployment `mizan-studio-feature-test.vercel.app`,
synthetic fixture tenant `owner-acceptance-test`. No production-business mutation, no merge to main.

## What shipped in this batch

1. **Gallery section layout** (simple Studio): a third per-section layout choice
   ("Image gallery") alongside Copy + image and Feature cards. 0-8 HTTPS image rows with
   alt text; rows left empty stay in the browser draft but are not published.
   - `model.ts`: `GalleryImage`, kind union extended, validation (safeImage, 8 max, alt <= 200).
   - `pagetree.ts`: one full-width lead column (eyebrow, level-2 heading, intro) + gallery block,
     desktop mode `grid`.
   - `fromtree.ts`: strict round trip branch; refuses gallery blocks with non-string image
     fields and any other unsupported shape (fail closed, unchanged tree).
   - Backend renderer already supported `gallery` nodes; verified offline (page_problems clean,
     render ok) and live.
2. **Page title editing**: the page panel has a "Page title" field for the page's title in the
   preview language. It rides the same draft save (`PUT /site/pages/{id}/draft` titles) and is
   part of the dirty/save identity: a title-only edit gates Publish and warns before leaving,
   exactly like a content edit. Brand name stays a global setting, never a rename.
3. **Switcher signposting**: every listed page is probed for simple-editability in the
   background; pages the simple editor cannot preserve are labeled "· opens read-only" in the
   switcher before they are opened. The read-only protection screen itself is unchanged
   (fail closed, no destructive conversion).
4. **Reset-password 500 fix** (security/account capability bug, found during V3):
   - Characterization (live, non-destructive): `POST /api/users/{id}/reset-password` returned
     404 for unknown users and 409 for the owner account, but 500 for ordinary staff users, and
     the password was NOT changed (transaction rolled back). The `hr_audit_log` table exists
     (`GET /api/hr/audit-log` 200). Root cause: the route's raw-SQL audit INSERT omitted `id`
     (and `tenant_id`); on this provisioned database those columns have no usable server
     default, so the INSERT raised and rolled back the password update.
   - Same defect class in the shared HR audit writer
     `activities/general/modules/hr/services/audit.py` (identical INSERT); fixed in the same
     commit: explicit `gen_random_uuid()` id, tenant from the acting user / RLS session setting.
   - Live E2E on the fixture tenant: created a throwaway user, reset password -> 204, old
     password 401, new password 200, audit row recorded with performed_by, user deleted. No
     reset actions were performed on unrelated users.
5. **Persistence label fix**: the "Backend snapshot saved / not saved" label kept comparing
   without the page title after title became part of the save identity; fixed so the label,
   Publish gating and the leave warning all compare the same key.

## Live verification (deployment rb2vt4dgv)

- UI-driven on `studio-second-page`: added a gallery section via the ordinary Studio UI
  (layout select, image rows, Save, Publish). Visitor page serves it:
  `/site/studio/studio-second-page` -> `<title>Second Studio Page</title>`, two gallery images
  with alt text.
- Page title: edited to "Second Studio Page" in the page panel, saved, published; visitor
  `<title>` and the switcher label both show the new title.
- Signposting: switcher shows "Hosted title acceptance", "Hosted no-code page" and
  "Mizan Studio visitor preview" with "· opens read-only"; both simple Studio pages unmarked.
- 390px (mobile emulation): no horizontal scroll, feature cards stack to one column, gallery
  renders 2-up, header/footer intact.
- Edit integrity: added a 4th feature card through the UI, saved, published; visitor serves all
  four card headings. Layout switch features -> gallery -> features preserved all four cards in
  the editor. Reload after saving round-trips clean (no protection screen). Leaving with
  unsaved layout-switch state triggered the beforeunload guard.
- Suites: studio vitest 132 passed (5 new: gallery round trip, emitted shape, empty-src drop,
  refusal paths, layout-switch preservation), shared backend pytest 95 passed.

## Publish/Make-public preflight (closes the silent-404 landmine)

`service.publish` and `service.set_public_access` now run the visitor contract
(`synthetic_scope_violations`: bound/provider nodes, mailto:/tel:, absolute URLs outside the
deployment's configured PUBLIC_SITE_HOST) BEFORE any mutation and refuse with a readable 422
naming the offending addresses. A failed publish adds no revision and leaves the published
snapshot serving; a failed Make-public leaves the page private. Private draft authoring is
unchanged (save never validates this), and the request-time 404 enforcement in
website_api/routers/public_pages.py stays as the backstop. Nothing was silently dropped and
the anonymous network/data scope is unchanged.

Live evidence (deployment is82m5vbo): gallery image set to an off-host URL -> draft saved
fine, Publish refused with "This page cannot be published for the public test host: it
references https://picsum.photos/... only allow addresses on <host> or relative links... the
previously published page is unchanged."; visitor kept serving the previous snapshot (verified
200 with the same-host images). Image pointed back at a same-host asset -> Save -> Publish
succeeded and the visitor serves it. Tests: 6 new in test_public_access.py (off-host/mailto
refusal without writes, same-host allowed, snapshot preservation, unconfigured-host skip);
backend suite 101 passed.

## Synthetic-content boundary discovered (design tension, reported not resolved)

The public route's synthetic scope refuses any page whose tree contains an absolute URL outside
the activation host (`_urls_stay_on_host`): a gallery (or split-section image) pointing at an
external HTTPS image makes the whole public page 404, with no publish-time warning in the
Studio. First observed live with picsum.photos images. CLOSED by the preflight above: publish and
Make-public now refuse off-host media with a readable error instead of a silent 404. The
fixture uses same-host assets (`/studio-assets/*.svg`). Remaining tension for the real-store
goal: genuine product imagery will usually be external, which synthetic scope cannot serve;
that is the connected-data/public-media decision, not error handling.

## Known gaps (unchanged unless noted)

- Gallery styling is fixed (grid, 2 columns, no captions beyond alt text); slider mode exists
  in the renderer but is not exposed in the simple Studio.
- Card/gallery per-kind data is kept when switching layouts (verified), but the seeded empty
  rows of an inactive kind stay in the browser draft until saved over.
- The `/erp/sw.js` service worker (scope /erp/) exists on the deployment; it does not control
  /studio/ but is worth watching if studio caching misbehaves.
- Reset-password sibling fix in the HR audit writer shares the defect class but its HR-module
  write paths were not exercised end to end (no HR fixture data).
