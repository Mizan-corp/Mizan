# Studio render parity and durable settings: checkpoint (WIP)

Status: INCOMPLETE branch, NOT for merge, NOT deployed, NOT validated from a clean clone. Branch: feat/studio-render-parity (off feat/s2-page-storage).

## Branch dependency warning
- feat/s2-page-storage has the backend site service, render and migrations v108, but none of the studio frontend.
- feat/studio-storage-client has the studio frontend (pagetree, fromtree, sitePages, studio.css) but NOT the backend site service.py or render.py. Its migrations.py is the same size as feat/s2-page-engine, so it is not stacked on feat/s2-page-storage.
- Neither earlier branch is a standalone runnable checkpoint. This branch carries both sides.

## What this branch contains
- Backend: SiteSettings model, migration v109 definition (the table is created only when the migration is applied), settings validation and upsert, GET/PUT /site/settings (site.manage), theme-aware renderer (font allowlist, radius), registry art/reverse settings.
- Studio frontend (system/frontend/src/features/studio): page-tree conversion, tree renderer (React) with parity to the Python renderer, site pages + settings client, inspector with theme controls and header links/actions/footer lines, tests.
- Test-only harness under shared/backend/tests/studio-harness (see its README).

## Verified (exercised, in the author's sandbox)
- Unit tests, studio folder: treerender 12, sitePages 14, fromtree 4, model 4, pagetree 4 (1 skipped) = 37 passed + 1 skipped. Whole frontend run (11 files, adds 6 lib test files) using the branch's own lib files: 54 passed + 1 skipped (the workspace-host test on this branch has 3 tests; my sandbox checkout had a newer 4-test variant that gave 55).
- DB suite: 14 checks passed (includes settings validation, single-row upsert, tenant isolation under RLS).
- e2e (15 steps): inspector edits to heading, accent, typeface, radius, header links/actions, footer lines; save; settings record present via API; storage wipe and reload restores all of it from the API; partial save failure (settings fault injected) is reported as "draft saved, settings FAILED"; publish is local test DB only; API down shows explicit failure.
- Parity: react vs shared Python renderer, same-width full-scroll, image-less and image-bearing fixtures: identical geometry and visuals (not byte-identical PNGs).

## Not verified / limits
- Clean clone: not done. No git clone is possible without repo credentials, and the GitHub archive zip could not be moved from the cloud browser to the test sandbox (the browser starts the download, but no download-transfer action exists). Instead the sandbox inputs were compared byte for byte with this branch fetched through the repository API: 17 of 19 present backend files under the harness's reduced app/ subset are identical, plus the 6 changed files and migrations. The 2 that differ are intentional harness shims: framework/loader.py (manifest_index only) and core/config.py (plain env settings). The 11 empty __init__.py files in that subset do not exist in the repo (namespace packages). The harness therefore runs a reduced backend subset with 2 shims, NOT the full backend app. On the frontend, 17 of 18 non-studio inputs (package.json, tsconfig, vitest/vite config, src/lib files and 5 of 6 lib tests) are identical. The workspace-host test differs, so the counts above use the branch's version. Before calling this ready, run npm install, vitest, run_db_tests.py and e2e.mjs from a fresh clone, and run the real app's test suite for the changed backend files.
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

## Validation closeout (23 November 2026)

The repository API fallback retrieved 1,935 backend files from a branch name. It was not a git clone, did not establish a pinned commit SHA, and did not prove a complete source tree. Directory previews are capped; code search is not an authoritative tree listing. Retrieval was stopped. Do not count these files as clean-checkout evidence.

One no-shim System API import was attempted using those files, with dummy local database settings. It failed immediately because the local Python environment lacks pydantic_settings. No dependency workaround, replacement settings class or loader shim was used in that attempt. Full-app import, startup, migrations and tests remain UNVERIFIED. Earlier reduced-harness results remain valid only within their stated scope.

### Reproduction prerequisites

Use a disposable Linux development environment with repository access, Git, Node 24 with npm, Python 3.12 or newer and venv/pip. The backend includes native dependencies, including WeasyPrint runtime libraries; follow the repository's Dockerfiles for those OS packages. Browser checks additionally need a local Chromium with CDP support. Use a fresh throwaway Postgres for database tests. Do not point any test at production or an existing development database. Do not copy a production .env or payment credentials into this checkout.

The commands below are a reproducibility recipe, NOT a record of successful execution. A maintainer must record the resolved SHA and results. Use a full 40-character commit SHA independently verified as the intended branch commit. Branch names can move.

```bash
git clone --branch feat/studio-render-parity --single-branch https://github.com/Mizan-corp/Mizan.git Mizan-studio-check
cd Mizan-studio-check
# Set this to the verified full commit SHA before continuing.
: "${EXPECTED_SHA:?Set the verified full commit SHA}"
git checkout --detach "$EXPECTED_SHA"
test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"
test -z "$(git status --porcelain)"
node --version
python3 --version
npm ci
npm exec -w system/frontend -- vitest run src/features/studio
npm exec -w system/frontend -- vitest run
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e shared/backend -e system/backend -e website/backend -e owner/backend -e admin/backend
python -m pip install -r shared/backend/requirements-dev.txt ruff
export DATABASE_URL=postgresql+asyncpg://ci:ci@127.0.0.1:5432/ci
export SECRET_KEY=ci-secret-key-not-for-production-32ch
# Import only. This dummy DB is not expected to exist. Do not start the app here.
for svc in system website owner admin; do
  (cd "$svc/backend" && python -c 'import main; print(len(main.app.routes), "routes")') || exit 1
done
ruff check shared/backend system/backend website/backend owner/backend admin/backend sdk/python --select E9,F63,F7,F82,F821,F601,F401,F841
```

Expected historical frontend count for this branch is 54 passed plus 1 skipped, including 37 passed plus 1 skipped in the studio folder. A changed count requires investigation, not automatic acceptance. The four full-app import commands and repository-wide lint above have NOT passed in this work. A successful import is not a successful startup or database migration.

### Reduced harness commands and limits

The following is a diagnostic recipe against the real checked-out app files, not a promise it passes without the two earlier shims. A failure must be recorded; do not insert those shims and call the result full-app validation. These scripts create a reduced schema and metadata stubs. Even a pass does not validate all app migrations or the complete app.

```bash
# From the checkout root, with .venv activated.
python -m pip install pgserver
export STUDIO_BACKEND_ROOT="$PWD/shared/backend"
export STUDIO_PGDATA="$(mktemp -d)"
export STUDIO_OUT="$(mktemp -d)"
python shared/backend/tests/studio-harness/run_db_tests.py
# Continue only after the DB checks pass.
python shared/backend/tests/studio-harness/serve_http.py
```

Keep that local-only API in a separate terminal. It binds 127.0.0.1:8791. It writes a throwaway local-test token into shared/backend/roundtrip_token.txt. Do not commit or share that token. In a second activated terminal from the same checkout root:

```bash
export MIZAN_SITE_BACKEND="$PWD/shared/backend"
export MIZAN_SITE_API=http://127.0.0.1:8791
export MIZAN_SITE_TOKEN="$(cat shared/backend/roundtrip_token.txt)"
cd system/frontend
npm exec -- vite --config vite.studio.config.ts
```

In a third terminal, start an isolated local Chromium (replace chromium with the installed executable name), then run the driver using Node 24. Set STUDIO_OUT to an existing writable directory. Do not reuse a personal browser profile.

```bash
chromium --headless --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --user-data-dir="$(mktemp -d)" about:blank
# In another terminal, from the checkout root:
STUDIO_OUT="$(mktemp -d)" node shared/backend/tests/studio-harness/e2e.mjs
```

Stop the local processes after testing. Delete the throwaway token and database only after all test processes are stopped. Keep logs and screenshots with the pinned SHA. The fault endpoint in serve_http.py must never be mounted in the production app.

### CI risk correction, no dispatch performed

ci.yml has no job-selection inputs. A manual dispatch runs all four jobs on the persistent shared self-hosted runner, including compose teardown with volume deletion and full e2e. It is not an isolated unit-test command. No CI, Deploy or Jobs workflow was dispatched in this work.

The workflow has no explicit secrets references, but that does NOT establish the self-hosted runner environment or default repository token permissions. Compose permits inherited payment environment values and defaults its payment host to Paymob's live endpoint. Therefore the earlier claim that CI cannot reach production or cannot receive production secrets was not established and must not be relied on.

Read-only inspection of the 39 retrieved e2e files found localhost API/browser targets and no non-localhost HTTP URL. The cross-app browser test leaves payment checkout outside its scope. This does not prove transitive backend code cannot call an external service. Dependency setup also downloads packages and browser/runtime binaries. A green CI run can satisfy the separate deployment workflow's same-SHA gate if someone manually dispatches deployment later; CI itself does not automatically dispatch it. No approval to run CI or deployment is implied by this document.

### Independent implementation work

While clean-source validation is blocked, the S3 studio work can continue as explicitly unmerged, unready branch work: style the header/footer inspector rows; expose the renderer's footer-link controls; add multi-page global-settings tests; and address the draft/settings partial-save design. R0 engine hardening, production preview/auth integration and R1 ERP integration remain separate unfinished gates. Test-mode commerce only. None of these UI tasks requires a CI dispatch, deployment or real payment.

## S3 follow-up: header/footer controls (23 November 2026)

Local exercise, still INCOMPLETE and not clean-source/full-app validated:
- Extracted ChromeInspector with stacked label/destination fields, counts, empty states, add/remove/reorder buttons and invalid-destination feedback. The inspector explains that saved settings are site-wide.
- Added optional footerLinks to the transitional editing model. Older projects remain compatible. Footer links pass through preview/settings serialization and restore, including explicit empty-list clearing. The existing renderer and backend validation are unchanged.
- Studio unit tests: 39 passed plus 1 skipped, including two new shared-settings mapping tests. The two page projects retain distinct content, get the same stored chrome and do not share mutable link objects.
- Reduced DB harness: 15 checks passed. The new check persists two distinct pages, commits site-wide header/footer settings, clears the session identity map, reloads and renders both pages with the shared chrome and distinct content. Still uses the reduced schema and two shims described above. It is not a full-app test.
- Local browser exercise: footer add/edit, local save/reload restoration, reorder, remove, invalid-destination feedback and preview rejection passed. Actual screenshot pixels were inspected. This pass used browser-only local persistence, not a new API e2e run.
- Reproducible driver: shared/backend/tests/studio-harness/chrome-controls.mjs. With local Vite and isolated Chromium CDP on 9222 as above, run `STUDIO_OUT=/path/to/existing/output node shared/backend/tests/studio-harness/chrome-controls.mjs`. It clears the isolated browser's local storage. Do not run it against a personal browser profile.

Multi-page UI selection/switching, live global-settings propagation to an already-open second page, full-app startup/migrations and clean-checkout validation remain UNVERIFIED. Existing two-request draft/settings save is unchanged. No CI, merge, PR, deployment, real order or payment.

## R0 follow-up: protect unsupported backend drafts

Source review found a destructive-save risk in the prototype, not evidence of actual data loss: an unsupported draft could fail to restore, yet remain the active backend save target for the unrelated browser copy. This is now blocked. Unsupported or archived pages, and page titles/languages the prototype cannot preserve, put the connection into a protected state. Backend save and publish are unavailable; a visible warning explains that the canvas is the browser copy, not the backend page. Local save/export stay available. A create conflict stops instead of adopting the conflicting page as a save target.

Reverse conversion now compares the reconstructed supported tree with the source, excluding generated node ids only. Extra blocks, rich markup, translations, custom button destinations, image alt text and uneditable device settings are refused rather than silently dropped. Literal entity-looking plain heading/button text is retained. This is conservative refusal, not support for editing those formats. The transitional editor and its generated ids are not a complete page-tree editor.

Local studio tests: 44 passed plus 1 skipped. New regression coverage checks protected targets and source immutability, rejected fields, and supported roundtrips. `protected-page.mjs` is a browser regression with MOCKED backend responses: warning visible, no backend Save/Publish buttons and zero write requests. It does not test a real backend or full-app persistence. Run with isolated local Vite/Chromium CDP as the other harness drivers; it clears that isolated profile's local storage. Actual screenshot pixels were inspected.

No new full-app, clean-source, concurrency, optimistic-locking, production-auth or API authorization claim. The two-request draft/settings save remains non-atomic. No CI, PR, merge or deployment.

## R0 follow-up: stable page identity, brand separation and loading

Page selection no longer derives from the mutable global brand. An explicit `?page=PAGE_ID` selects that exact backend identity. Without one, only a sole existing page is selected; an empty list permits initial creation. Multiple pages without a choice, or a missing explicit identity, block backend writes instead of picking a fallback. After supported load or save, the current page ID is retained in the URL. This is not a page-management or switching UI.

Existing page titles are preserved on draft save, independent of brand changes. A single supported-language title need not match the brand (this supersedes the prior conservative brand-equality restriction). Multiple languages, unsupported trees and archived pages remain protected. Changing preview language to a different page language blocks saving rather than overwriting titles. Initial loading makes editor and top actions inert so a delayed response cannot replace newly typed edits. A create conflict still stops without adopting the conflicting identity.

Local studio tests: 48 passed plus 1 skipped. `page-identity.mjs` is a MOCKED browser regression covering delayed-loading guards, changed-brand restore with an independent page title, same-ID save/reload, ambiguous/stale selection refusal and create-conflict with no draft overwrite. Actual loading and restored-state screenshot pixels were inspected. The API responses are mocked, not new live persistence evidence. Run with local Vite and isolated Chromium CDP as the other drivers; the driver clears isolated localStorage and never sends writes to a real backend. No test demonstrates full page management, simultaneous edits, optimistic locking or startup in the full app.

Clean-source/full-app validation remains blocked. No CI, PR, merge, deployment or real payment.

## R0 follow-up: serialized save/publish and snapshot-aware notices

A synchronous single-editor operation gate now rejects overlapping backend save/publish attempts, including repeat clicks before the busy state renders. Buttons show the operation state. Save clones one snapshot and uses it for both existing draft/settings requests. Editing may continue during the operation. Completion compares the saved snapshot with the current editor and explicitly warns when newer changes remain unsaved. It never replaces newer editor content with the response.

Publish requires the current editor snapshot to have a known complete draft/settings save (or supported loaded tree/settings). Initial blank pages or failed settings loads are not considered ready. Starting a save invalidates readiness until both requests succeed. Partial failure leaves Publish disabled and the existing precise failure notice intact. Retry is possible after cleanup. If edits arrive while Publish is in flight, completion says those newer edits are neither saved nor published. Publishing is still local test DB only.

Local studio tests: 50 passed plus 1 skipped. Isolated studio Vite build passed. `save-snapshot.mjs` uses MOCKED API responses to exercise repeated clicks, editing during delayed save/publish, dirty publish refusal, partial settings failure and successful retry. Actual screenshot pixels were inspected: newer content remains visible, the earlier-snapshot warning is explicit, Publish is disabled. Run with the same isolated local Vite/Chromium CDP setup; it clears isolated localStorage and overrides confirmation in that isolated test page. It does not call real backend endpoints.

This gate is not an atomic backend transaction, an optimistic lock, a cross-tab/session lock or protection against another client's writes. Two-request draft/settings atomicity and cross-session concurrency remain unfinished. No new live API, full-app or clean-source validation. No CI, PR, merge, deployment or real payment.

## R0 follow-up: leaving and separate persistence status

The editor now keeps browser-save and backend-save indicators separate. Local save updates only the browser indicator. Backend save updates only the known complete backend snapshot. A beforeunload listener requests browser confirmation for unsaved changes or an in-flight operation. When connected, browser-only save does not clear a backend dirty warning because reload currently prefers backend data. No automatic browser or backend saving was added.

A localStorage quota/write failure retains editor text, leaves the browser indicator unsaved and displays a persistent export-before-leaving error. Successful retry clears it. Local studio tests: 53 passed plus 1 skipped; isolated studio build passed. `leave-guard.mjs` uses a mocked offline backend and mocked quota failure. It tests cancellation of a synthetic beforeunload event, retained text and retry. Actual screenshot pixels inspected. Native confirmation UI was not tested. Browsers may suppress beforeunload prompts, especially on mobile or process termination; this is best-effort protection, not a backup or recovery guarantee. Export or successful persistence is still needed.

## Acceptance reconciliation and next larger milestone

This is a checkpoint against ADR-015 D13 S2/S3 and the current branch's stated R0 engine-hardening scope, not a declaration that R0 is complete. No completed local micro-slice closes a broader gate by itself.

| Gate | Current evidence | Still required |
| --- | --- | --- |
| One canonical page-tree and faithful authoring | Python tree renderer, TS conversion and conservative refusal tests; source data protected when unsupported | Tree-native editing preserving node IDs, full supported settings/content/languages and arbitrary supported compositions without lossy reconstruction |
| Draft storage, tenant boundaries, revisions | API/storage implementation and reduced DB checks, including RLS and shared settings across two persisted pages | Full-app database migrations/startup/tests and authenticated integration; no shim-based completion claim |
| Save/publish correctness | Explicit partial-failure reporting, operation serialization and snapshot-aware notices | Atomic draft/settings contract, revision/concurrency policy and cross-session conflict handling; client gate is not a backend lock |
| Session resilience | Separate local/backend indicators, storage failure handling and best-effort leave guard | Durable recovery design, safe recovery choice when browser/server differ and broader navigation/mobile testing |
| Global style and chrome | Theme/header/footer controls, footer links and shared settings rendering tests | Full global-settings coverage, page switching/live propagation and end-to-end roundtrips under the real app |
| Renderer/device/SEO/service | Existing renderer and parity fixtures for the supported subset | Responsive service integration, complete supported-block semantics, CSP/auth, public published-only routes, caching/purge and route SEO as ADR scope requires |
| Studio workflows | Section editing, preview, undo, local profiles/export/import and local-test save/publish | Full sections/columns/blocks authoring, redo/autosave/revision UI, media/layout controls and broader keyboard/mobile behavior |
| Reproducibility and release readiness | Branch files byte-verified; scoped local tests and screenshots with explicit limits | Complete pinned-source install, full app tests and integration verification; currently BLOCKED. No CI/deploy authorization implied |

Next meaningful implementation milestone proposed: a tree-native authoring core for the supported layout/text/image/button subset, retaining every original node ID and field, with explicit edit operations rather than whole-tree reconstruction. Acceptance should include two differently composed pages, a changed node/setting saved and reloaded without unrelated JSON changes, undo/redo preserving IDs, and refusal without mutation for unsupported edits. This moves toward the ordinary user's full no-code outcome instead of adding more notice-only changes. It is not full page management, R1 ERP integration or completion of all blocks. Scope and sequence need review before implementation. Atomicity/concurrency and full-app validation remain parallel gates, not silently deferred or marked complete.

## Tree-native authoring core milestone (bounded, experimental)

Opt-in local URL: open the existing studio entry with `?editor=tree&page=PAGE_ID` against the loopback test backend. It requires an explicit existing page with a supported tree. It is a separate native-tree editing path, not another persisted format. The original Project prototype and its conservative unsupported-data safeguards remain unchanged.

Supported native subset: section/columns/column layout and heading/text/image/button leaves, English/Arabic content fields, and the enumerated desktop/tablet/mobile settings from the current registry subset. Native edits clone the original tree and change only the chosen field or setting. Every original node ID and every untouched field remains intact. The node list and preview select nodes directly. Undo/redo retain complete native trees. Draft save sends only `{tree}`, never regenerated titles or global settings. Returned tree equality is checked semantically, allowing object-key ordering differences. No publish or global-style controls in this mode. No node add/delete/reorder, page create/switching, full rich-text toolbar, theme editing or complete format support is claimed.

Unsupported types, invalid/duplicate IDs, unsupported settings/content, excessive sizes/depth and unsafe edited URLs refuse without source mutation. Unknown metadata is conservatively protected, not dropped. This frontend subset check is not a replacement for the backend validator or a security certification. Server validation remains required.

### Scoped acceptance evidence

- Studio unit tests: 59 passed plus 1 skipped. Native core tests cover two distinct compositions, one-field-only immutable edits, original IDs/translations/rich text/alt/settings retained, per-device edit isolation, undo/redo and nonmutating refusal. Client test checks native draft save sends only the tree.
- Focused NativeStudio TypeScript check passed; isolated studio Vite build passed. Neither is a full app typecheck/build.
- `native-authoring.mjs` uses MOCKED sessionStorage-backed API responses for two distinct compositions. It edits, undo/redoes, saves/reloads and compares the entire tree with an expected one-field-only edit. Unsupported load makes no writes. Actual illustrated and alternate-composition screenshot pixels inspected.
- Reduced DB harness now has 16 checks. Check 16 saves/reloads two tree JSON drafts through the real service, preserving all expected fields and multilingual titles. This is a service/DB complement to the mocked browser test, NOT one live browser-to-API end-to-end test. The known reduced schema and two shims remain in use.
- `native-guards.mjs` explicitly tests the NEW entry point with mocked responses: missing identity no request, loading/archived/wrong identity cannot save, repeated native Save serialized, edits during delayed save retained and reported unsaved, failed/mismatched save echo keeps dirty content and retry available. Synthetic beforeunload cancellation tested for dirty/in-flight state and removed after exact save. Native browser confirmation dialog not tested, best-effort caveat still applies.

All drivers require the existing isolated local Vite/Chromium CDP setup. They mock API responses, not production data. Native authoring uses sessionStorage for its test server simulation only, not app persistence. Existing backend atomicity/cross-session concurrency and full-app/clean-source/release-validation gates remain open. R0 is NOT complete. No CI, PR, merge, deploy, real orders or payment.

This milestone establishes a bounded native editing core with scoped evidence, not replacement readiness for the full prototype. Next integration must build on this tree-native state rather than expand the lossy reconstruction path. Larger remaining authoring work includes native structural operations, field-appropriate no-code controls, global theme/chrome preservation/integration, revision/publish workflows and real authenticated full-app validation.
