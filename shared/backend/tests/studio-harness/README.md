# Studio harness (TEST-ONLY, not production code)

Local-only scripts that exercise the web studio against the site storage API and a throwaway Postgres.
Nothing here is imported by the app. WIP on an INCOMPLETE branch, not for merge.

Environment (all optional; defaults are the original sandbox paths):
- STUDIO_BACKEND_ROOT: directory that contains app/ (shared/backend in this repo)
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
