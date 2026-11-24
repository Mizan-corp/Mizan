# Technical business composition

Status: LOCAL ONLY, not checkpointed or deployed, 24 November 2026 12:13 Cairo.

The user rejected the visual quality of the plain instructional kit. It remains supported for compatibility, not design acceptance.

A separate first-party `tech-business-v0` composition has four native S2 pages: Home, Products, Services, Contact. Original sample SVG illustrations and sample copy are included. No actual stock, prices, business claims, contact destination, repair workflow or checkout is connected. This is not allwirya visual or functional parity.

Preview links switch only between the four staged pages. Creation makes four unpublished drafts and preserves current shared settings. A second, explicit all-pages confirmation applies the reviewed sample design and navigation, using the settings token captured at review, so a newer settings edit must conflict rather than be overwritten. This setting save is not atomic with draft creation and is never described as such. Failed/unverified writes freeze retries until refresh.

NativeStudio private preview resolves exact same-workspace draft addresses against the current page list and opens via the existing unsaved-change guards. External and missing destinations remain inert. Editor mode still selects header/footer for editing. There is no visitor runtime or new public route.

Fresh real local JWT/API/UI acceptance passes: preview and traverse all four, create four without settings effects, explicit shared save, native heading edit/save/reload, private draft navigation across three pages, mobile390 no page overflow, no pageerrors. Existing pages/settings restored by verified outer transaction rollback; test credentials deleted. Reviewed-token conflict preserves a newer shared design and freezes retry; duplicate install409 leaves page list exact. Independent PostgreSQL transactions prove simultaneous same-prefix create-once/409, separate-tenant isolation, forcedRLS and third-page failure with zero partial writes. Disposable schema removed. The first concurrency harness used pooled connections with session search_path and failed refresh; retaining one connection per transaction corrected harness scope, not app behavior.

Four pure backend tests and 205 Studio tests/1skip pass. Actual local Studio desktop/mobile pixels inspected after explicit mirrored h2/h3 scale fixes, and visible mobile return-to-editor control exercised. Original sample SVG drawings are illustrative, not product photos. This is a coherent first-party composition, still not a full business-ready website or visual benchmark acceptance.
Remaining: final source/test checkpoint, isolated hosted acceptance and exact cleanup before canonical promotion. No production, commerce or spending.


## Hosted composition checkpoint, 24 November 2026 12:24 Cairo

The composition and private preview traversal are hosted on the isolated test project, source `50dcd6b1b869cc16bfe108cf8c29235d9e541077`, deployment `dpl_7w84QswkLE2jQ73hYu3V7qZbPmi1`. Canonical https://mizan-studio-feature-test.vercel.app/studio-preview.html . Hosted owner UI exercised preview/traverse/create4, explicit separate shared-design save, native edit/save/reload, private3page traversal, mobile390 and return to editor, duplicate409. All4known unpublished fixture pages removed with no revisions; exact original pages retained and shared design restored, credentials deleted. Entire ERP artifact retained byte-identically. No functional storefront or benchmark acceptance claim.

## Native card-surface followup, 12:30 Cairo

LOCAL ONLY pending source checkpoint and hosted proof: column background uses existing `background`, `card`, `primary` roles and an independent boolean `rounded`. Platform registry, native authoring validation and both renderers agree. Existing pages are unchanged. Technical sample uses these native controls for service/catalog/contact cards. Real local UI changed a card to primary and square, saved/reloaded and verified retained settings, with exact rollback afterward. Five backend unit tests,120Studio tests/1skip, typecheck/build pass. Narrow navigation wraps with readable44px targets and reduced mobile gap/font. Final local390px pixels rechecked. Extra hosted preview-only check identified the narrow292px clipping case and images captured before lazy load; those images were not accepted as proof. Current new local visual harness waits for illustration decode. Next release must prove these changes on the isolated host before promotion.
