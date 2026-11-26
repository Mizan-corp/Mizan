# Studio harness (TEST-ONLY, not production code)

Local-only scripts that exercise the web studio against the site storage API and a throwaway Postgres.
Nothing here is imported by the app. WIP on an INCOMPLETE branch, not for merge.

Environment (all optional; defaults are the original sandbox paths):
- STUDIO_BACKEND_ROOT: directory that contains app/ (system/core/backend in this repo)
- STUDIO_PGDATA: pgserver data dir for the throwaway database
- STUDIO_OUT: directory where screenshots are written (default /downloads)
- FIXTURE: parity-img fixture json (default ../fixtures/fixture-image.json)

Scripts:
- run_db_tests.py: applies migrations (incl. v109 site_settings) and runs 14 DB checks (pages CRUD, RLS tenant isolation, settings validation, upsert roundtrip, settings RLS). Needs: pip install pgserver psycopg2-binary sqlalchemy fastapi.
- serve_http.py: real FastAPI + JWT auth server on :8791 for the studio. It contains a TEST-ONLY fault switch (POST /__test/fail-settings) that makes PUT /site/settings return 500, to prove partial-save reporting. Never mount this in a real app.
- e2e.mjs: Chrome DevTools driver, 15 steps: inspector edit, save, API settings record, partial failure, storage wipe + reload restore (theme + custom header links/actions + footer), publish (local test DB only), API-down failure.
- parity.mjs / parity-img.mjs: paired react vs shared Python renderer captures. They hide scrollbars in the shared tab only (a capture condition, NOT a production layout fix).

Run order: start serve_http.py, start vite with vite.studio.config.ts (MIZAN_SITE_API, MIZAN_SITE_TOKEN from roundtrip_token.txt, MIZAN_SITE_BACKEND), start headless Chrome with --remote-debugging-port=9222, then node e2e.mjs.

Follow-up driver: chrome-controls.mjs exercises footer link add/edit, local save/reload,
reordering, removal, invalid destination feedback and preview rejection. It clears local
storage in the isolated browser profile. Start local Vite and Chromium CDP on 9222,
then run STUDIO_OUT=/path/to/existing/output node chrome-controls.mjs. Browser-only
persistence, not an API e2e or full-app test. run_db_tests.py now has 15 checks,
including two persisted pages rendering one shared settings record.

protected-page.mjs: MOCKED backend unsupported-tree regression, checks a visible
protection warning, absent backend save/publish controls and zero API writes.
Uses local Vite + isolated Chromium CDP on 9222. Clears that profile's localStorage.
Not a live backend or full-app test. STUDIO_OUT selects the screenshot directory.

page-identity.mjs: MOCKED API regression for delayed load guards, stable page ID
selection/save/reload despite changed brand, preserved independent page titles,
ambiguous/missing target refusal and create conflict without draft overwrite.
Uses isolated local Vite/Chromium CDP and clears isolated localStorage.

save-snapshot.mjs: MOCKED delayed API regression for serialized save/publish,
newer edits while operations run, dirty publish refusal, partial settings failure
and retry. Uses isolated local Vite/Chromium CDP, clears localStorage, overrides
confirmation only in that test page. Not atomicity or cross-session validation.

leave-guard.mjs: mocked offline/local quota-failure test for distinct browser vs
backend status, dirty synthetic beforeunload cancellation, retained edits and retry.
Native browser dialog is NOT tested. Prompts are browser-dependent and best effort.
No automatic saves. Use isolated local Vite/Chromium CDP as above.

native-authoring.mjs: MOCKED sessionStorage-backed API for two distinct native-tree
compositions. Checks one-field-only JSON change, stable IDs, undo/redo, save/reload
and unsupported load refusal. native-guards.mjs checks the NEW native entry's loading,
archived/wrong/missing identity, serialized saves, newer edits, failure/echo mismatch,
retry and synthetic beforeunload. Both require isolated local Vite/Chromium CDP.
These are not live API e2e. run_db_tests.py now has 16 reduced checks, adding native
JSON save/reload through the service while preserving fields and multilingual titles.


native-structure.mjs: MOCKED native structural/content/saved-theme test. Checks add,
move, remove/undo with stable IDs, rich field and selected-text Italic toolbar action,
URL refusal/acceptance, media description, save/reload, read-only saved chrome/theme
and zero global settings writes. Exports /tmp/native-structural-tree.json for a
separate real page_problems validator check. Local Vite + isolated CDP only;
not authenticated live API e2e. No upload, purchase, Publish or deployment.


native-drag.mjs: MOCKED native mouse palette insertion, visible marker, compatible
node cross-column move and sibling reorder, undo, Escape cancellation, Enter/Tab
position activation, CDP-emulated touch insertion/handle move and draft save/reload.
Not physical-touch or screen-reader acceptance. No edge auto-scroll. Uses same
isolated Vite/CDP setup, never production accounts.


native-hover.mjs: MOCKED real mouse deepest-node hover/click, separate selection
border, ancestor breadcrumb selection and inspector sync. Screenshot evidence.
Uses isolated Vite/CDP; no real API or physical-device accessibility claim.


native-ux.mjs: MOCKED semantic sidebar/ready section acceptance. Preset insertion,
undo/redo, fresh IDs, content-derived layer names, editable heading, save/reload.
Exports /tmp/native-preset-tree.json for separate real backend page_problems check.
All native drivers now select nodes via data-node-id/type, not visible technical IDs.


native-real.mjs: REAL reduced loopback API native acceptance, no fetch mock. Requires
serve_http.py seeded local reduced API on8791, Vite bridge configured with its local
test token, isolated CDP. Exact tree save/reload; other-session conditional write;
stale native rejection retaining local/server content; exported unsaved JSON check;
deliberate reload/fresh save. Writes only throwaway local DB and /downloads export.
Same reduced schema/config+loader shims, NOT full-app validation. run_db_tests.py
now17checks, adding two independent session race/stale rejection/fresh retry/tenancy.
Legacy callers without expected_token remain unprotected from later overwrite.


native-simple.mjs: MOCKED canvas-first default smoke: panels closed, truthful
local save state, Add/preset, relevant editing with technical settings collapsed,
closing panels keeps dirtiness, Save updates state. Other drivers use + Add and
Save after simplification. Not nontechnical-user usability proof.

`native-canva.mjs` checks the Canva-directed rail and focused dock, actual canvas pointer selection, contextual Layout, content edit/save and 390px mobile sheet/no document overflow. Uses the same mocked local Vite/CDP harness as native-simple; not full-app acceptance.

`native-library.mjs` verifies ready-block search/insert, complete native template preview and reversible apply/save/reload, keyboard/mobile preview, Explorer search/list failure retry and dirty-switch guards. Its API is mocked. `native-real.mjs` now also verifies template persistence and Explorer against the actual reduced authenticated router/service/DB, still not the full application.

`native-motion.mjs`: constrained motion CSS playback and reduced-motion/browser persistence plus Python-exported document check. Run `check_motion.py` first to generate the exported fixture after native-library generated its category trees. `STUDIO_BACKEND_ROOT` and `STUDIO_WORK_ROOT` select local reduced API/source roots. This is a reduced harness, not full application validation.
