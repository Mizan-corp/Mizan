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


## Native structural/content/saved-appearance milestone

The opt-in native entry now supports adding rows, columns and heading/text/image/button children in permitted positions, sibling reorder and confirmed subtree removal. Existing IDs are retained; new nodes get unique valid IDs. A new row includes one column. Last-column removal is refused (remove the row instead), and the root cannot be removed. Add/remove updates only that row's desktop column count. Full-tree undo/redo covers these edits. Unsupported metadata/types/settings are still safely refused, not silently discarded or claimed editable.

Field-appropriate controls include plain heading/button/alt fields, rich-text visual editing with Bold/Italic/Bullets, validated link/image addresses applied on blur and a media thumbnail. Stored rich markup is unchanged until that field is edited; edited HTML is sanitized. No media upload/library/purchase, arbitrary block system or complete rich editor is claimed. Toolbar formatting uses the browser editing command API and needs broader cross-browser validation.

Saved theme and header/footer are fetched after page validation and displayed read-only. Theme-load failure is explicitly labeled as defaults. Native draft save still writes tree only, never global settings or titles. Existing unknown/unowned theme data is untouched. No theme accessibility certification: the acceptance fixture's white CTA text on bright lime accent is difficult to read. Stored appearance was deliberately preserved, not silently changed. Theme editing and contrast warnings remain future work.

Scoped evidence: studio 64 passed + 1 skipped; focused NativeStudio TypeScript and isolated studio build passed. Mocked native-structure browser exercise covers stable added ID, sibling move/remove/undo, rich content and real selection Italic toolbar action, unsafe link refusal, valid link, image description, save/reload and saved chrome/theme with zero settings writes. New-row JSON is checked separately by the real backend page validator. Native authoring and NEW-entry guard regressions rerun successfully after appearance loading. These remain mocked browser plus standalone validator evidence, not live native-browser-to-API e2e, full app or clean-checkout validation. Prior reduced DB evidence remains 16 checks; not rerun for this UI-only milestone.

Native Publish, page create/switching, media management, theme editing, cross-session conflict handling, atomic multi-resource save, full format support and full-app/release validation remain open. R0 remains INCOMPLETE. No CI, PR, merge, deployment, real orders or spending.


User steering after this milestone: actual drag-and-drop is required for adding and moving elements, not merely Add/Move buttons. Next native implementation must cover palette-to-canvas insertion, compatible cross-container moves, visible drop positions and undo, preserving IDs/schema and guards. Pointer/touch and keyboard access need explicit design and tests. None is implemented or verified by the button-based milestone above.


## Native drag-and-drop milestone (bounded)

Native preview now accepts pointer palette insertion and existing-node sibling reorder or compatible cross-container move. Blue marker shows insertion position before release. Original subtree IDs and fields remain intact. Root/self-descendant/invalid containment, last source-column and target overflow are refused by the core. Undo/redo reuse native history; no second persistence model.

For touch, tap to select, then drag the explicit Move selected handle. Handles use touch-action:none; preview itself retains normal touch scrolling. Keyboard users choose a palette item or selected-node move, expand Keyboard/click drop positions and activate a labeled position. Escape and pointercancel cancel. This fallback is intentionally explicit, not a claim of full screen-reader accessibility. Palette stays sticky in the preview. Edge auto-scroll is not implemented, so long-page moves may require the keyboard/click destination list or scrolling before dragging. Narrow viewport and physical mobile ergonomics are not yet accepted.

Scoped checks: 65 studio passed + 1 skipped, focused TypeScript, isolated studio build. MOCKED native-drag.mjs uses real CDP mouse input for palette insertion, visible marker, compatible cross-column move, sibling reorder and undo; Escape cancellation; Enter/Tab activation of palette/position; CDP-emulated touch insertion and selected-node-handle move; tree draft save/reload. Native structure, authoring and guard drivers rerun successfully. Touch emulation is not a physical device test. Keyboard test is not screen-reader proof. Existing low-contrast theme caveat remains. No full-app/live API e2e, clean-source or cross-session/atomicity claim. No CI, PR, merge, deploy or spend.


## Approved hover and nested-selection UX

Ordinary preview hover now outlines the deepest wrapped node with an amber dashed outline and node-type label. Selected node has a distinct purple solid border and Selected label. Blue remains reserved for the drag insertion marker. Labels are CSS pseudo-elements with pointer-events:none, so no extra hit surface covers elements. Breadcrumb above preview exposes section > columns > column > leaf; clicking any ancestor selects that exact node and updates inspector/list/outline. Nodes under overlapping content still need outline/breadcrumb access. Flat left list is not yet an expandable tree.

MOCKED native-hover.mjs uses real mouse input to verify deepest heading hover and click selection, separate selected state, ancestor column breadcrumb selection and inspector sync, with screenshots inspected. Native drag driver rerun to verify overlays do not break pointer/touch/keyboard insertion/moves. Status now stops saying Dragging after a simple select with no drop. 65 studio tests + 1 skipped unchanged; focused TypeScript/isolated build and native guard regressions retain scoped limits. No full keyboard/screen-reader/physical-device accessibility claim. No data/settings writes added by hover or selection.


## Cohesive visual-builder UX checkpoint

Working interpretation of the user's Elementor/Canva/WordPress direction: approachable direct canvas editing, contextual tools, clear hierarchy and editable ready sections, not a clone of any named product or arbitrary-positioning mandate. Native core is retained.

Add/Layers sidebar tabs separate the integrated draggable palette and three ready sections (Intro + image, Image + story, Call to action) from an indented collapsible outline. Layer names come from content, with semantic Page/Section/Column/Heading/Text/Image/Button labels. Source IDs are available only in Advanced element details. Contextual canvas Move/Earlier/Later controls and ancestor breadcrumb remain. Native section presets use existing registered blocks and generated unique IDs, no external media. They are ordinary editable native content with undo/redo and save/reload, not a second format or complete template library. Existing tree data is not regenerated.

67 studio tests plus 1 skipped. New preset unit tests cover unique IDs, preserved prior content, undo and names. Mocked native-ux.mjs exercises insert/undo/redo, live readable name update, edit, save/reload and integrated palette; exported preset JSON passes the real backend page validator. Mocked native-authoring/native-guards/native-structure/native-drag/native-hover drivers rerun after semantic selectors were updated to data-node-id/type, rather than visible technical IDs. Removed redundant outer click handling that could override deepest-child selection after sidebar portal events. Focused NativeStudio TypeScript and isolated studio build passed. Screenshot pixels inspected for Add panel and nested Layers with edited preset.

Still experimental desktop authoring subset. Inspector layout settings remain technical enumerations; no arbitrary custom blocks, complete templates, page management, native Publish, media upload or module data binding in this milestone. No physical mobile/screen-reader/full-app/live API/clean-source acceptance. Existing low-contrast theme and no edge auto-scroll caveats remain. Atomicity/concurrency/release gates stay open; R0 incomplete. No CI, PR, merge, deployment or spend.


## Bounded native draft concurrency and real reduced-API acceptance

Page details now return an opaque SHA-256 edit_token over canonical sorted compact JSON containing page ID, status, titles, draft, published tree and updated_at. Native saves require a 64-character token and submit expected_token. Server gets a fresh row under SELECT FOR UPDATE with populate_existing, compares before mutation and rejects stale snapshots with 409. Successful saves return next token. All current service page mutators (draft, publish, rollback, archive, reopen) participate in the row lock. No migration. Native editor refuses a backend without a token, preserving loading/identity/read-only guards.

On conflict, local content stays in the editor and remains dirty; Save pauses. Explicit Export my unsaved tree downloads exact current tree. No automatic overwrite, merge or reload. User deliberately reloads to adopt server state after exporting. Export is an advanced JSON recovery artifact, not a completed ordinary-user conflict merge workflow.

Important limits: expected_token remains optional in service/router for legacy compatibility. An unconditional legacy/API caller can overwrite later; row locks alone do not prevent it. This closes bounded native-vs-native stale draft writes, not universal all-client concurrency or atomic draft/settings. A token is a snapshot fingerprint, not a monotonic generation/revision log. updated_at normally changes on mutation and reduces ABA, but identical restored snapshot/timestamp can reproduce a token. Canonicalization ignores JSON object-key order, preserves array order, and does not promise cross-language numeric/unicode normalization. Token compares server-issued strings, never client recomputation. Hash collisions are not designed as an auth boundary; tenant/auth scoping still applies. Settings are excluded and remain read-only in native mode. Publish/revision policy and multi-resource atomicity remain unfinished.

Evidence: studio 68 passed +1 skipped, focused TypeScript and isolated studio build. Reduced DB 17 checks pass, adding a real two-independent-session race with stale identity-map entries: exactly one succeeds, one 409, server nonmutation on stale retry, deliberate fresh-token save, tenant-isolated 404. Existing lifecycle checks still pass. Real native browser-to-loopback API test uses actual reduced router/service/auth/tenancy/Postgres, with no fetch mock. It saves/reloads exact one-field tree, simulates another authenticated client save, proves stale native rejection and retained local/server content, verifies downloaded unsaved-tree contents, then deliberately reloads and saves fresh. Actual conflict/saved screenshots inspected. Six mocked native drivers rerun with token-shaped fixtures (not proof of concurrency themselves), including missing-token load refusal.

This real reduced e2e closes the prior mock-only native browser path gap within its harness. It is NOT full-app startup/auth/migration/deployment or clean-source validation: same reduced schema, config shim and loader shim apply. No blocked retrieval/CI route restarted. No CI, PR, merge, deploy, real order or spend. R0 remains incomplete.


## Simpler canvas-first default after user complexity feedback

Default opens with canvas, + Add, Layers, undo/redo, Save and one plain saved/unsaved state. Both side panels start closed. Add and Layers open on demand and can close independently. Selecting content opens relevant edit fields; arrange/remove and technical layout/device settings are collapsed. Routine diagnostic strips move to a disclosure; the always-visible boundary says Test copy, not your live website. No public publishing implied. Real failures and conflicts remain visible, not hidden with routine notices. Hover/selection, contextual moves and breadcrumbs remain available. Root has no distracting selected border. Selected layer scrolls into view.

New mocked native-simple.mjs checks default hidden panels, truthful local save state, Add/preset, contextual edit, closed advanced controls, closing panels retaining dirtiness and successful save status. All six earlier mocked native drivers pass with updated Add/Save selectors. Real reduced API e2e/export/conflict/fresh-save rerun passes and conflict screenshot inspected: clear conflict/export and retained content remain visible in simpler layout. 68 unit tests +1 skipped; focused TypeScript and isolated build pass. This is a design iteration and interaction regression, not ordinary-user usability testing or full-app/physical-device/accessibility acceptance. Saved fixture lime CTA still has low contrast; stored appearance preserved, accessibility not certified. No new backend contract or permission changes.


## Canva-directed workspace checkpoint (2026-11-23)

The user's explicit Canva direction replaces the mixed-reference shell. Reference: Canva's own editor announcement at https://www.canva.com/newsroom/news/glow-up/ and its embedded before/after video, visually inspected. This is a 2024 official reference, not a claim that every current Canva account has this exact interface. No Canva branding or media was incorporated.

The native editor now has a persistent labeled tool rail, one focused left dock for Add/Layers/content, a neutral central workspace, a compact gradient header, and a contextual selected-element toolbar. Layout opens the existing device-specific controls; Earlier/Later preserve native structure semantics. Add and Layers temporarily replace the content dock instead of competing with a second inspector. Ordinary canvas selection does not enter move mode. Mobile uses a bottom sheet while the rail/canvas remain accessible. Website flow, responsive modes, nested selection, native tree IDs and save guards are unchanged. The test-copy/not-online label and plain saved/unsaved state remain; real errors and conflict/export remain visible.

Validation: 68 unit tests passed, one skipped; focused TypeScript check and isolated Vite build; all six existing native mocked drivers; simpler-default driver; new native-canva.mjs (actual canvas pointer selection, one-dock switching, contextual Layout, content dirty state/save, 390px sheet and document overflow check); real reduced API/auth/DB native save/conflict/export driver. The drag driver explicitly reopens Add after selecting an element, matching the new focused-dock behavior. Actual default, Add, edit, mobile and real-conflict pixels inspected. These checks are not ordinary-user research or complete responsive/accessibility acceptance. Saved fixture's low-contrast green CTA remains a known theme/accessibility limitation. No public publish/deploy, CI, PR, merge, or spending. Full-app, clean-source and original R0 acceptance remain incomplete.


## Functional native library and Explorer checkpoint (2026-11-23)

The user's expanded capability clarification keeps Explorer, complete templates, ready UI blocks and animation packs in the overall builder outcome. The Canva shell alone does not complete these. This checkpoint supplies a first functioning library and Explorer slice; animation packs, larger catalogs, media management, module binding and full site authoring remain unfinished.

- Ready blocks: six searchable/category-filtered native sections: Intro + image, Image + story, Call to action, Three benefits, Featured quote and Contact invitation. Each appends ordinary editable tree nodes, preserves every prior node, allocates unique IDs and supports undo/redo/save/reload. Individual draggable elements remain in a disclosure.
- Templates: three complete four-section page-body compositions (Independent studio, Creative services, Journal & ideas), full rendered preview, explicit replacement confirmation and undo/redo. Applying changes the body only, preserves page/root identity, root metadata/settings, titles and shared site appearance. New IDs are reserved against all old IDs too. Starter copy is English, and apply switches content view to English. This is a starter catalog, not a complete design marketplace or whole multi-page site/theme template system.
- Explorer: actual current-workspace page-list API, title/slug search, status/current-page, refresh and explicit page switching. Unsaved switching asks before discarding; cancel retains local work. Save-in-progress switching is disabled. Archived pages cannot be opened for editing. Loading/switching clears the mutation target, errors remain visible, and Explorer can recover to a supported page. No create/rename/archive UI is claimed.
- Preview modal is outside canvas/editor DOM, uses the same rendered tree/styles and isolated preview IDs to avoid selection/DnD collisions. Escape, focus trapping and mobile stacked preview/footer tested. Shared theme is shown read-only. No external media/assets downloaded.

Evidence: 72 unit tests passed, one skipped; focused TypeScript and isolated Vite build. Eight prior native mock drivers pass after opening Individual elements where appropriate. New `native-library.mjs` exercises block search/insert, template preview nonmutation/cancel/apply/undo/redo/save/reload, modal keyboard/mobile behavior, Explorer search/archived disable/list failure/retry and unsaved-switch cancel/confirmed identity. The real reduced API/auth/DB driver now also creates a second actual page, lists/switches/returns through Explorer and persists/reloads an applied complete template with unchanged root identity. Original real conflict/export still passes. Actual desktop blocks/templates/preview, 390px mobile preview and real Explorer screenshots visually inspected. A broken first modal preview and unstacked mobile preview were fixed and checked again, not accepted from DOM assertions alone.

Limits: reduced schema/config and loader shims remain; this is not full-app, clean-source, physical-mobile, screen-reader or ordinary-user acceptance. Saved theme low-contrast CTA caveat remains. Legacy unconditional writers remain outside native token protection. No CI, PR, merge, deploy, production publication, orders or spending. Full R0/no-code outcome remains INCOMPLETE.

### User-confirmed direct card interaction

After the first local library preview, the user explicitly requested removing card buttons. Cards now click/Enter/Space to preview, drag onto the native page to insert at the visible position, and inserted canvas elements click to customize. Template drag deliberately confirms body replacement; it never silently destroys current composition. The modal retains explicit Apply/Cancel as keyboard alternatives and a deliberate replacement decision, not permanent card clutter. Actual pointer and emulated-touch ready-section drags, template drag, no-preview-on-drop, native insertion index, and original-content undo are exercised. No placeholder navigation was added for animation packs.


## Function-based body block catalog (2026-11-23)

The next user request names Hero sections, Feedback, Login, Headers and Footers and asks to continue by function. Body catalog now has 18 entries, with two variants each for Hero sections, Feedback, Features, Pricing, FAQ, Contact, Galleries and Teams, plus story/callout. Search and category chips filter actual editable native compositions. Card click/keyboard preview and pointer/touch drag insertion stay unchanged. All 18 generated trees pass the real platform `page_problems` validator, unique-ID/content-preservation/undo tests and existing native rendering semantics. Actual category and pricing-preview screenshots inspected.

This catalog does not mark the request complete: Login, shared Headers/Footers, animation packs and richer component behavior remain open. Pricing is sample copy plus enquiry links, not checkout; quotes and team profiles are visibly sample content; gallery uses editable registered decorative art, not downloaded portraits/photos; FAQ answers are visible content, not an accordion. Shared Header/Footer replacements cannot be silently inserted into one page body. A Login visual layout must not claim authentication is connected. Larger catalog, actual media/auth/module binding and full release acceptance remain unfinished. No new backend format, public writes or spend.


## Constrained entrance-motion contract (2026-11-23)

This first motion set is functional, not a placeholder tab, and does not complete the broader animation-pack requirement. Platform and SDK registries now share constrained animation (none/fade/rise/slide/zoom), speed (quick/normal/slow) and delay (none/short/long) settings on registered blocks. Existing SDK reverse/variant/art schema drift found during this check is aligned with platform, preserving the platform's supported contract. SDK and platform manifests are byte-identical. No arbitrary script, CSS value, external pack URL or infinite-loop token is accepted.

Native Animate panel saves per-device settings with ordinary tree history/token-protected draft save. A replayable sample demonstrates the effect while the editing canvas stays still to avoid moving pointer targets. Python/React renderers emit identical allowlisted motion classes and finite CSS keyframes; published/exported documents animate once at load, no scroll trigger. Reduced-motion preferences disable all effects and leave content visible. Nested nodes reset default timing rather than accidentally inheriting parent speed/delay. Desktop settings inherit to devices unless overridden.

Evidence: 74 unit passed, one skipped; focused TS/isolated build; all prior native/library mocks; new `native-motion.mjs` checks real CSS playback, static editing canvas, reduced-motion computed style and visible content, mocked save/reload, and actual Python-exported HTML playback/final state. `check_motion.py` checks SDK/platform exact schemas, all five effects accepted, invalid token refused, per-device override and Python renderer classes/reduced-motion CSS. Real reduced API driver verifies motion token saved and reloaded before existing template/Explorer/conflict/export checks. Actual Animate and export pixels inspected. This is not full app, browser-matrix, screen-reader or complete motion-pack/timeline/scroll-system acceptance. Login/shared Headers/Footers remain open. No CI, PR, merge, deploy, public publish, purchase or spend.
