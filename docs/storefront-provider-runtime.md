# First module-provider runtime slice

Status: EXPERIMENTAL FIRST SCALAR SLICE, hosted isolated acceptance passed 24 November 2026; save+preview+runtime wiring for the versioned bindings envelope completed 25 November 2026 (see the wiring checkpoint at the end). Not full builder/storefront readiness. Earlier local-only sections below are development history; this status and the final hosted checkpoint supersede those deployment-state notes.

## Scope and ownership

The platform owns a trusted ProviderRegistry and generic projection of native heading text. A declaration does not supply a URL, SQL, import path, callable, grant, or module activation. Only platform-reviewed Python registrations supply callables. The site module owns its optional storefront/contract.json and provider.py in its own folder. Existing module layout is unchanged. The experimental declaration schema remains experimental.

The first real source is site.appearance.brand, the explicitly saved website brand, not a legal company name or inferred tenant name. The provider returns that single nullable field and nothing else from settings. It verifies that the bound database tenant is the explicit requested tenant. Authenticated API consumers must hold site.manage. There is no public unauthenticated route, product publication policy, inventory provider, collection item context, price/URL/media/action runtime, cart, or checkout.

A platform-core provider can be registered independently of the tenant's active business module list. Other providers require active module membership. Both the classification and provider callable are platform code, never declarative metadata. Production discovery must also account for current module registry status, activity/variant compatibility and package version negotiation before supporting external module packages. No auto-import/discovery of arbitrary packages is supplied here.

## Implemented locally

- ProviderRegistry validates reviewed contracts, copies metadata, filters inactive module discovery, rejects incompatible type/meaning/cardinality and unknown fields, and reads through an explicit immutable tenant/language context. Values are not cached across tenants.
- Provider results fail closed on additional fields, missing required values, nontext values or excessive length. Missing nullable brand resolves to explicit empty or hide. Exceptions are errors, not fallback to another tenant or a private source.
- Site-owned provider reads existing tenant-scoped site settings with an explicit tenant-context check and no writes.
- Authenticated discovery and resolve router is drafted but deliberately not mounted. Resolve accepts only the trusted target key heading.text, not an arbitrary target semantic supplied by a client.
- Binding projection accepts a bounded candidate bindings envelope keyed by language and property, strips it into an ordinary S2 tree, runs the actual static platform page validator, checks every binding before reading any provider, then resolves the selected language into a copied tree. Hide removes the leaf in the rendered copy. Static stored content and other languages stay unchanged. Source values must be escaped as text by the renderer.

## Verification so far

Five asynchronous registry tests, five binding-projection/renderer tests using the actual current platform page validator, and twelve existing offline contract tests pass. Checks cover invalid context, inactive/unknown source denial before provider access, tenant-separated calls, projection leakage denial, metadata copy protection, null/empty/hide, unsupported targets and malformed native trees. These are backend tests, not actual browser acceptance.

Read-only real isolated database provider checks bound each of the two existing test tenants in turn, compared the returned brand with that tenant's saved website settings, and proved that a mismatched requested tenant was refused in both cases. No data was written and no credentials are included in this source package.

## Remaining before hosted feature acceptance

1. ~~Complete the local versioned page-binding schema review, support provider compatibility validation at save and preview, and preserve existing unsupported/static pages without reconstruction.~~ Done 25 November 2026: hosted save validates and persists the versioned envelope, authenticated preview resolves it, the visitor runtime resolves it per request under activation policy, and publish is policy-aware instead of a blanket refusal (see the wiring checkpoint).
2. Mount authenticated discovery only after permission/API tests and server preview resolution are exercised. Apply current active module registry and versions before more providers are admitted.
3. Expand actual API tenant/permission, inactive source, source error and conflict tests. Python renderer escaping of resolved text now has a passing test. Dynamic renderer values must never become markup or trigger commands.
4. Add Static/Dynamic controls in Studio with source recommendations, explicit missing behavior, preview error handling, dirty/undo/save/conflict protection. Use actual rendered synthetic examples, no private customer values in thumbnails.
5. Prove real isolated API plus local UI, checkpoint exact source, deploy to the existing isolated project without changing other application entries, then hosted edit/save/reload/render and ERP regression with screenshots.
6. Collections, public product publication, prices/currency, related pages and commands are separate further slices. The retired legacy storefront router remains unmounted.

No claim of benchmark recreation or ready storefront follows from these foundations.

## Save/preview/runtime wiring checkpoint (25 November 2026)

The versioned bindings envelope (mizan.page-bindings.experimental.v0 and siblings) is now wired end to end:

- Save: save_draft and publish validate bound-source compatibility before any write (check_bound_tree), unchanged.
- Preview: the authenticated /site/data/preview route resolves bound trees for site.manage users, unchanged.
- Runtime: the visitor route (website_api/routers/public_pages.py) resolves bound trees per request, re-reading consent and module activation every time, when the page's activation allows connected data. No current flow can create such an activation: set_public_access pins allow_connected_data=False, and enabling connected data stays a separate, explicitly approved operation.
- Publish: the blanket refusal of dynamic drafts is replaced with a policy-aware check. A bound tree publishes freely for authenticated preview EXCEPT when an enabled activation already covers the page: the synthetic request-time boundary refuses bound trees, so publishing would silently break a live public URL. That one case is refused with a readable 409 before any mutation, keeping the previous published snapshot. Make-public still refuses bound published trees outright, so public connected-data exposure remains impossible through every existing flow.

Offline tests: six new cases in shared/backend/tests/test_public_access.py (publish allowed without activation, refused with an enabled activation, allowed without a configured host, include_bound flag behavior, off-host preflight preserved); the twenty-three visitor-runtime tests (including allow_data=True resolution and synthetic refusal) pass unchanged. No deployment or activation-contract change is part of this wiring.

## Latest local checkpoint

The native page validator has an explicit versioned bindings extension. SDK/platform manifest copies are byte-identical. Raw unresolved dynamic trees are refused by the renderer even with validate=False; only authorized resolved copies render. No existing backend service or hosted deployment was changed. The next integration must validate every bound source at save and preview, mount the authenticated router, and only then expose UI controls.

## Local integration checkpoint

Local service create/save/rollback/publish paths now validate bound source compatibility before writes. Publishing a dynamic draft is explicitly refused until public service resolution exists. Local authenticated router includes discovery, scalar resolution and Python-rendered preview. This is NOT deployed. Hosted service still has its previous static schema and UI.

A real local FastAPI application with the existing authentication dependency and isolated database passed unauthenticated401, normal owner-test login, discovery200, bound heading preview200, unknown private-field422 on preview and draft save, and exact unchanged stored tree/edit-token after the rejected save. No valid bound tree was persisted and no settings/ERP data were changed. This is not browser/UI acceptance or a non-owner403 test. The next step is403/tenant-route tests plus Static/Dynamic UI and local API save/reload acceptance before a source checkpoint or isolated deployment.

## Local UI checkpoint

The local Studio has Static/Dynamic heading controls, compatible scalar text source search, explicit missing hide/empty, preserved static text, undo history, and authorized server-resolved native preview. Failure/loading hides unresolved content instead of showing stale values. Preview-only dynamic publish limitation is shown. Source card uses a rendered synthetic Aa heading example, not private data. This is not a complete recommendation image library.

Local actual frontend plus local actual authenticated API plus real isolated DB exercised Dynamic source selection, Save/reload exact binding with retained static heading data, actual empty saved-brand hide behavior and publish409. After acceptance, the experimental binding was REMOVED from the existing throwaway draft so the unchanged older hosted editor could still open it. The static tree and title remain intact. No website settings were changed. A settled reload screenshot exists, but positive nonempty provider UI is still unverified. Earlier screenshot capture at loading was discarded and replaced with settled evidence.

Frontend100tests pass/1skip and TS/build pass. Three local API permission-dependency tests use an overridden authenticated principal with no grants and prove403 for discovery/resolve/preview. This is not real non-owner session acceptance. Previous normal-owner real-login and401 checks used actual auth. Full cross-tenant route tests, nonempty provider UI, local mobile/failure tests, conflict/undo interaction, full source checkpoint and isolated deployment/regression remain pending. No hosted dynamic binding feature exists yet.

Actual owner-session cross-tenant API check also passed: fetching an existing page in the other isolated tenant returned404; client-supplied tenant_id on resolve returned422 because extra fields are forbidden. The same normal-login actual preview/private-field rejection suite passed again, with original stored page token/tree unchanged. Positive nonempty brand UI remains unverified.

## Preview hardening and desktop/mobile failure checks

Frontend now accepts only an exact structural projection of the submitted native tree. Unknown node properties, settings changes, changed static content, extra/moved nodes or unresolved binding envelopes fail closed. Only the bound heading value may change; removal requires that heading's hide policy. One new unit test covers replacement refusal. Frontend101tests pass/1skip.

Actual local browser1440/390 mocked-provider interaction passed compatible source search, nonempty dynamic heading, retained Static toggle, source outage with no stale/static fallback, and conflict409 save freeze. Screenshots inspected. This is mocked positive UI, not hosted positive API/UI.

The real database provider also passed a nonempty-brand check in a transaction that was flushed then rolled back for each existing test tenant. No settings change was committed. This verifies actual provider nonempty projection separately from the mocked UI; do not merge those claims into end-to-end positive UI proof. Original per-tenant empty brand state remains the live state. A full positive real API/UI run still needs a controlled throwaway fixture or transaction-scoped harness.

## Positive real API/UI acceptance

Normal owner-test browser login against the local actual API and real isolated database passed selecting Dynamic saved-brand source, saving and reloading the exact persisted binding, and displaying a nonempty actual saved brand. A temporary website brand fixture was set only in the throwaway owner tenant through the token-protected settings API. Exact original settings were restored and verified after acceptance, and the experimental page binding was removed from the throwaway draft for compatibility with the older hosted editor. No other tenant or original page was changed. Dynamic publishing returned409 as designed. This is positive LOCAL actual API/UI evidence, not hosted deployment proof.

## Hosted isolated checkpoint, 24 November 2026

Hosted candidate dpl_4SCA6Ur8Jxb6GAcjidABiNGfYzRD passed actual normal owner-test UI Dynamic source selection, Save/reload exact binding, and nonempty real provider preview at https://mizan-studio-feature-test.vercel.app/ . Corrected source26files were verified byte-exact at commit ae5340e537a4ab6607a65ee888afb5635a3c8c0c. Fourteen accidental duplicate-path additions from the checkpoint procedure were verified as our own content, removed, and confirmed absent at that commit. No unrelated files or user material were removed.

Hosted mobile390 controls and preview were inspected; no physical-device acceptance claimed. Existing ERP normal login/products settled empty state passed. Anonymous data discovery401 and health database-connected verified. Temporary brand fixture was set only in the throwaway owner tenant using CSRF and expected-token protection, exact original settings restored and verified after test, and experimental page binding removed from that throwaway page. The original Studio tenant was not changed. Temporary credential files were removed.

Final tests: frontend101passed/1skip, backend22passed, focused TS/build passed. Local browser desktop/mobile source failure and409 save-conflict checks passed. The actual authenticated cross-tenant page request returned404 and client-provided tenant override422. Three no-grant principal dependency checks returned403, labeled as dependency tests rather than real non-owner login.

This slice supports only scalar plain-text heading binding to site-owned saved website brand. It does not support product collections, prices/currency, media, commands, cart/checkout, general package discovery or public dynamic publishing. Dynamic publish stays409 until public site-service resolution exists. It is a first real no-code data binding, not benchmark recreation or full readiness. Rollback deployment is dpl_9jN8ZgUBxKaHjELPjTTBJdt7gxHi. Other application frontend entries, API adapters and routing config were preserved byte-for-byte; the shared site backend changed only for this experimental binding slice.

### Known limitation: activation key is per deployment host, not per tenant

`site_activation` is unique on `(host, slug, page_path)` with no `tenant_id`
in the key. That is safe only because each deployment's `PUBLIC_SITE_HOST` is
a single-tenant host (the isolated test host today). A future multi-tenant
shared host would let one tenant's toggle collide with another tenant's row;
that needs a grounded schema plan (tenant in the key) before any such host is
configured. Recorded per review finding F2; no schema redesign without that
plan.
