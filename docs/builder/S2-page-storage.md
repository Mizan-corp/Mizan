# S2 page storage: pages, drafts, publish, revisions

Status: **INCOMPLETE. Not ready to merge or deploy.** Branch work for ADR-015 step S2
(storage part), on top of `feat/s2-page-engine`. What remains before this can merge is
listed at the end.

## What this adds

The storage half of the page-engine contract (`docs/builder/page-engine.md`, "Storage and
revisions"), in `app/platform/site/`:

- `models.py` — `site_pages` (id, slug, titles per language, status, draft tree, published
  tree) and `site_page_revisions` (immutable publish snapshots), both `TenantScoped` with
  row-level security like every workspace table (#112 pattern).
- `service.py` — create, save draft (autosave), publish, list revisions, rollback, archive,
  reopen. One business operation per function, one transaction, Arabic `HTTPException`s
  (`docs/MODULE_STANDARD.md`).
- `router.py` — `/site/pages` REST for the studio, every route behind the workspace
  permission `site.manage`, which the module's `manifest.json` declares (the loader mounts
  the router like it mounts `themes`).
- `manifest.json` — module `site`, kind `platform`, declaring `site.manage`.
- Migration `v108_site_pages` in `app/db/migrations.py` — both tables with
  `ENABLE`/`FORCE ROW LEVEL SECURITY` and the standard `tenant_isolation` policy.
- `app/models/registry.py` — registers the models for metadata-wide operations.
- `system/backend/tests/test_site_storage.py` — validation tests that run anywhere, and
  draft/publish/revision/rollback/isolation lifecycle tests that run against the database
  (`DATABASE_URL`), following the themes tests.

## Behaviour, per the contract

- Autosave and save write the **draft only**; nothing reaches the public site until
  publish.
- **Publish** validates the draft with the SDK-shared validator
  (`app/framework/manifest.page_problems`, ADR-016 D4), copies it to the published tree,
  writes an immutable revision, and marks the page published.
- **Rollback** copies a revision into the draft; the published tree changes only on the
  next publish.
- Pages are **archived, never deleted**; revisions are never updated or deleted.
- Every stored tree is validated and size-bounded (200 KB, the bound the studio's preview
  bridge enforces). Markup inside text fields is a render-time concern: the server renderer
  sanitises with nh3 (`app/platform/site/render.py`).
- Slugs are lower-case latin (`a-z0-9-`), unique per workspace; titles are per language
  (`ar`, `en` first, ADR-015 D7).

## Verified locally (23 Nov 2026, throwaway local Postgres, documented subset harness)

- DB layer, 11/11 checks: draft-only saves, publish with immutable revisions 1 then 2,
  rollback, archive/reopen, duplicate-slug 409, per-request tenant binding, cross-workspace
  isolation, and raw SQL as the `mizan_app` NOBYPASSRLS role under FORCE RLS seeing only
  the bound workspace's rows.
- HTTP layer, 15/15 checks through a real FastAPI app mounting this branch's real
  router/service/auth chain with real JWTs and real role resolution: 401 without/with an
  invalid token, 403 for a role without `site.manage`, the full lifecycle over HTTP,
  duplicate-slug 409, invalid-tree 422, archive blocks edits, and workspace isolation.
- That testing caught a real bug, fixed in `service.py`: after UPDATE commits,
  `updated_at` (a `func.now()` onupdate) is expired, and the router reading it to
  serialize the response was implicit IO that breaks under async; the service now
  refreshes the page inside the session after update commits.
- Harness scope: local Postgres with a documented subset schema (auth tables from the
  real models, a manifest_index-only loader shim, a harness JWT secret). This is not the
  full backend suite, not CI, and the migration has never run on a real database.

## Not done yet (before merge)

- The migration is committed but **not applied anywhere real** (CI or a managed database).
- **Edge-cache purge on publish** (Cloudflare, ADR-015 D6) is out of scope here; it belongs
  to the site service that will serve public pages.
- The public read path (serve the published tree through the renderer by slug) is part of
  the site service step, not this storage step.
- Studio wiring: the typed client exists on `feat/studio-storage-client` (unit-tested and
  round-tripped against the local harness stack), but the studio UI does not call it yet
  and still saves to localStorage only.
- Full backend test suite and CI on the branch.
