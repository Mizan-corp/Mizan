# Isolated Vercel test deployment

This records the existing Studio + ERP test deployment. INCOMPLETE product acceptance. Not a production deployment or a merge-ready branch.

## Build and package

From a full feature-branch checkout, with Node 22+, Python 3.12+ and the repository dependencies installed:

```sh
npm ci
cd system/frontend
npx vite build --config vite.preview.config.ts --outDir /tmp/mizan-studio-build
VITE_API_URL=/api VITE_BASE=/erp/ npx vite build --outDir /tmp/mizan-erp-build
cd ../..
python deploy/studio-test/package.py --repo . --studio-build /tmp/mizan-studio-build --erp-build /tmp/mizan-erp-build --output /tmp/mizan-package
```

Use fresh build/output directories. The packager refuses an existing output directory. Review the output before uploading. It copies the real shared backend and system routers, not a reduced Studio-only API. The API adapter removes the external /api prefix and retains the normal application middleware, authentication, CSRF and tenant enforcement. Static ERP routes use /erp/. The explicit VITE_API_URL=/api is required because the repository production env file otherwise targets the existing external API. The Studio entry is the default root.

The packager does not create a database, run migrations, seed data, link an account or deploy. Deployment requires the separately approved isolated test project and its own environment settings. Do not copy production secrets, .env files, CLI credentials, generated auth cookies, uploads or existing private business data into this package. Never commit those values. Configure secrets directly in the hosting environment through its secure settings.

A fresh database requires a separate reviewed additive schema/bootstrap process and a test account. That process is NOT reproduced by this packager. Do not run destructive migrations or assume the production database is an acceptable target.

The packager also rejects an ERP JavaScript bundle containing the existing external system API URL. This guard prevents a missing build-time override from silently targeting the wrong backend.

The historical test deployment used the hosting CLI from the package directory after its project and isolated environment were configured. Running a deploy is a separate action, not part of this script. No paid plan is required or authorized by these instructions. Private organization Git import can offer a paid plan. Stop rather than starting a trial or checkout.

## Recorded state, 2026-11-24 Cairo

Existing test entry: https://mizan-studio-feature-test.vercel.app/

Recorded deployment: dpl_BQ64WaSAYbcDKkoKAfyTvkfv8z6q, https://vercel.com/ammar0xfs-projects/mizan-studio-feature-test/BQ64WaSAYbcDKkoKAfyTvkfv8z6q

Studio code and build entry/config were subsequently preserved on this branch. The live deployment was not changed by those preservation commits. Known backend corrections: use settings.is_production for session-cookie secure flags; remove import of a nonexistent site_analytics models module. Neither change disables CSRF, authentication or tenant policies.

Verified earlier: Studio login, saved heading reload, desktop and emulated-touch reorder/insert/save, invalid-drop/Escape preservation, and basic phone controls. Earlier focused tests: 89 pass, 1 skip. Only the test playground was used for content mutations; the original home page was retained.

Still incomplete: full ERP business acceptance, hosted owner/admin frontends, account-boundary coverage, physical iOS keyboard verification, full clean-checkout reproduction of the isolated database bootstrap and hosted environment. A built bundle and a registered API route are not acceptance evidence. Do not call this full product readiness.

The current source preservation step compares pinned remote files with deployed/local files. Minor final-brace whitespace can differ in UI-edited files and must not be described as byte-exact. This recipe is a reproducibility aid, not evidence that a fresh full checkout has passed end-to-end deployment.

## Visitor-runtime packaging correction, 2026-11-25 01:20 Cairo

The synthetic visitor runtime (commit 88aeda3, website/backend/website_api/routers/public_pages.py) was never served by this deployment: the packager copied only shared/backend/app and system_api, api/index.py mounted only the system router, and vercel.json routed only /api/* to Python. Every /site/* request fell through to a Vercel edge NOT_FOUND. That universal edge-404 was never evidence of the activation privacy policy or of functional publishing, and any earlier observation that treated it as such is invalid and retracted.

The recipe now copies website_api into the function, mounts public_pages on the same app, and routes /site/* to it (commit 8217f02). Verified live on the test host, anonymous requests, 2026-11-25 ~01:19 Cairo: enabled synthetic fixture https://mizan-studio-feature-test.vercel.app/site/studio/welcome returns 200 with its static content, the runtime CSP (default-src 'none', frame-ancestors 'none') and cache-control: private, no-store; disabling its activation returns the app-level 404 {"detail":"Not found"}; re-enabling returns 200. Bound pages stay un-publicizable (publish refusal and fail-closed activation refusal from the page-bindings policy commits).

Proven slices, kept distinct: (1) bound save/reload, authenticated preview and private publish of pages carrying the mizan.page-bindings.experimental.v0 envelope; (2) the static synthetic public runtime above. Dynamic connected-data public rendering remains deliberately unproven and blocked: allow_connected_data is pinned false and any change requires separate explicit approval. Single-tenant host limitation stands (the activation key has no tenant dimension).

## Deploy pipeline: fail-closed script and 2026-11-25 01:35 incident

Use deploy/studio-test/deploy.sh for every deploy of this host. It builds the
three entries with their required bases (preview /, studio /studio/, erp
/erp/), REFUSES to package any entry HTML carrying relative asset refs (the
signature of a missing --base flag), runs the prune and the static-manifest
guard un-piped under set -euo pipefail so a guard failure aborts before any
deploy, and only then runs the hosting CLI. The guard verdict must never pass
through a pipe that masks its exit status.

Incident, 2026-11-25 01:35 Cairo: a manual deploy chain piped the manifest
guard through tail, masking its non-zero verdict; the studio bundle had been
built without --base=/studio/, so /studio/studio.html referenced relative
asset paths and the /studio/ entry served a broken app for ~100 seconds until
the corrected redeploy at 01:37. The main editor, API and visitor runtime
were unaffected (the broken refs were confined to /studio/studio.html).
Remediation: the base check and fail-closed chaining are executable in
deploy.sh, verified against an intentionally bad entry.

Historical discrepancy (unresolved, recorded 2026-11-25 02:31): /studio/?page=...
rendered the legacy shell successfully at 00:34 (reviewer screenshot), but every
committed vercel.json has routed only the catch-all to /static/$1 and package.py
has never produced static/studio/index.html, so committed config alone would
always edge-404 /studio/. The likely serving file came from an earlier manual
rsync deploy's static tree and was removed by the first fail-closed prune
(01:42); no file listing of the 00:34 deployment survives to prove which file
served it. /studio/ was therefore never an intentional canonical entry: the
studio app entry is /studio/studio.html. Do not cite /studio/ 404 behavior,
in either direction, as evidence of routing intent.

Known-good route matrix (verified live 2026-11-25 01:41 Cairo):
- /                    200  Studio preview SPA (sign-in, home, editor)
- /api/*               Python function (401 unauthenticated, CSRF on writes)
- /site/studio/<slug>  visitor runtime: 200 only while the page's synthetic
                       activation is enabled; app-level 404 otherwise
- /studio/studio.html  200  Studio app entry (base /studio/)
- /erp/                200  ERP SPA (base /erp/)
- /admin/ /owner/ /website/  200  augmented frontends
- anything else        hosting edge 404 (never evidence of app behavior)

F3 concurrency evidence (tests/test_public_access_concurrency.py): the real
publish() and set_public_access() were run against a real local Postgres in
both lock interleavings with observed blocking and correct refusals; the
binding provider-chain validator (check_bound_tree) is patched out in those
two tests only - it is covered by the mocked suites and needs tables outside
the minimal concurrency schema. Do not describe the F3 proof as exercising
provider validation.

## Recovery checkpoint, 2026-11-24 00:28 Cairo

Test deployment dpl_FKwr7EWS5kXc3QEQEu1NgdpdfYws restores explicit same-origin API targeting and fixes settings login-preview links with React Router useHref so /erp/ is retained. Verified actual Studio editor, ERP products empty state, settings preview URL and same-origin API reads. This supersedes the historical deployment ID above. No settings or business transaction was changed. Owner/admin frontends and distinct-account boundary acceptance remain incomplete.

## v1 typed card-repeat browser proof, 2026-11-25 03:35 Cairo

Two-half live proof on the canonical test host (signed-in, config-h), fixture
page "Card repeat proof" (id 5f264ca1-a4aa-4d2e-86d8-db51593940e0, slug
card-repeat-proof), kept as an intentional static fixture:

- Zero-grant half (accepted 03:23): repeat attached with zero consent grants;
  authenticated preview rendered EMPTY (row pruned, zero-grant privacy
  behavior); reload persistence verified; repeat then removed and page saved
  back to static.
- Positive half (accepted 03:35, NAME+PRICE only): two synthetic fixture
  products created via ERP UI ("Fixture Card Widget" 42.50, "Fixture Card
  Gadget" 17.00), catalog selection + display consent (show_price, EGP,
  both products; images never enabled) saved via the studio Data panel with
  the bilingual v1 confirm wording; repeat re-attached; in-editor canvas and
  authenticated private preview both rendered two repeated cards with real
  names and EGP prices (pixel-verified).

IMAGE SLOT NOT PROVEN: product image upload is refused by design on this host
(shared/backend/app/framework/files.py: on Vercel without
BLOB_READ_WRITE_TOKEN, uploads return 503 "file storage not configured"
rather than silently losing the file). No no-code path can create the
WorkspaceFile product_image provenance the provider requires, so repeated
image pixels were not exercised and must not be claimed.

Restore (same run, verified by authenticated GET): consent effective values
back to exact zero-grant {products: [], show_price: false, show_image: false,
currency: null}; catalog selection back to {products: [], categories: []};
both fixture products deactivated (records remain, inactive, reversible; no
DB cleanup). Metadata deltas, not exact database restoration: edit_tokens on
both settings rows changed - post-restore cards edit_token 7bd57827...6b3c,
catalog 8a5789a4...3aca. Fixture products persist as inactive records
("Fixture Card Widget", "Fixture Card Gadget") in the studio-test workspace.
