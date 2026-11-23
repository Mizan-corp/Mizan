# Studio render parity and durable settings: checkpoint (WIP)

Status: INCOMPLETE branch, NOT for merge, NOT deployed, NOT validated from a clean clone. Branch: feat/studio-render-parity (off feat/s2-page-storage).

## Branch dependency warning
- feat/s2-page-storage has the backend site service, render and migrations v108, but none of the studio frontend.
- feat/studio-storage-client has the studio frontend (pagetree, fromtree, sitePages, studio.css) but NOT the backend site service.py or render.py. Its migrations.py is the same size as feat/s2-page-engine, so it is not stacked on feat/s2-page-storage.
- Neither earlier branch is a standalone runnable checkpoint. This branch carries both sides.

## What this branch contains
- Backend: SiteSettings model, migration v109, settings validation and upsert, GET/PUT /site/settings (site.manage), theme-aware renderer (font allowlist, radius), registry art/reverse settings.
- Studio frontend (system/frontend/src/features/studio): page-tree conversion, tree renderer (React) with parity to the Python renderer, site pages + settings client, inspector with theme controls and header links/actions/footer lines, tests.
- Test-only harness under shared/backend/tests/studio-harness (see its README).

## Verified (exercised, in the author's sandbox)
- Unit tests, studio folder: treerender 12, sitePages 14, fromtree 4, model 4, pagetree 4 (1 skipped) = 37 passed + 1 skipped. Whole frontend run (11 files, adds lib tests): 55 passed + 1 skipped.
- DB suite: 14 checks passed (includes settings validation, single-row upsert, tenant isolation under RLS).
- e2e (15 steps): inspector edits to heading, accent, typeface, radius, header links/actions, footer lines; save; settings record present via API; storage wipe and reload restores all of it from the API; partial save failure (settings fault injected) is reported as "draft saved, settings FAILED"; publish is local test DB only; API down shows explicit failure.
- Parity: react vs shared Python renderer, same-width full-scroll, image-less and image-bearing fixtures: identical geometry and visuals (not byte-identical PNGs).

## Not verified / limits
- Clean clone: not done. The tests ran in a sandbox using a local copy of the backend with the branch files overlaid, byte-identical to this branch. A real clone needs repo credentials the sandbox lacks. Run npm install, vitest, run_db_tests.py and e2e.mjs from a fresh clone before calling this ready.
- Repo-wide tsc has pre-existing errors in src/App.tsx (missing inventory screen modules), none in studio files.
- Draft and settings are saved in two non-atomic requests. Partial failure is reported explicitly and tested.
- Chrome (header/footer) is one settings row per tenant. Multi-page and tenant-wide behavior is unverified, and the studio exercises one page.
- Header link and footer editor rows are unstyled and rough.
- Footer links (supported by the backend) are not in the studio UI.
- Language toggle changes direction only. Content is not translated.
- R0 engine hardening and global settings are NOT complete. ERP integration (R1) is not done.
- Parity captures hide scrollbars in the shared tab only. This is a harness capture condition, not a production layout fix.
- The harness fault switch (/__test/fail-settings) is test-only and lives in the harness server, not in the app package.
- No merge, deploy, spend or security changes were made.
