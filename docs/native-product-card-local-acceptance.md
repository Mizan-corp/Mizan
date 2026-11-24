# Native product-card preview: local acceptance, 24 November 2026

Status: LOCAL ACCEPTANCE, isolated source checkpoint in progress, NOT DEPLOYED. No production, commerce or payment changes.

## Contract

A card is an ordinary editable native column in its own columns row, with direct heading/text/image child targets. The persisted column carries an exact versioned `mizan.page-card.experimental.v0` language map. A registered trusted inventory source expands it into a render copy, not a separate page format or a persisted snapshot.

The name-only product/category selection remains independent. A second exact inventory-owned website-card policy defaults empty, price off, image off, currency unset. Dedicated GET/PUT controls require site.manage, inventory permission, verified active module and tenant. Writes lock tenant and compare an edit token. Generic settings hides and refuses the policy key.

Price reads retail_price only after explicit price consent. It requires exact decimal string/Decimal, canonical two decimals, nonnegative bounded amount and explicit EGP/USD/EUR/GBP/SAR/AED. The currency is a label, not FX, tax or checkout calculation. Costs and wholesale price never enter the projection.

Image reads image_url only after explicit image consent and requires an exact WorkspaceFile tenant, product owner, product_image kind, same URL and raster MIME match. Typed URL rules allow only tenant product-image uploads or tenant paths on public Vercel Blob storage. Private paths, unrelated hosts, SVG, query/fragment/credentials, traversal and encoded paths are refused. No server-side fetch.

All languages, scopes, targets and aggregate native bounds are checked before product reads. One card template, 1 to 6 items. Scalar headings outside the card can compose; nested scalar bindings and heading repeats are refused. Missing optional fields are removed, no static fallback. Missing configured language refuses preview. Empty records remove the row. Native tree and byte bounds rechecked after projection. Public dynamic publish stays409 and raw renderer refuses unresolved metadata.

## Evidence

- Four typed value tests, five pure native projection tests, six actual-model provider tests and six actual-import async runtime tests pass.
- Existing composition/collection regression subset: 20 tests pass including the value/projection tests above.
- Frontend 198 pass, 1 skipped, TypeScript passes.
- ERP build passes with VITE_API_URL=/api and VITE_BASE=/erp/. Studio static build passes.
- Actual normal owner login plus ordinary UI: add Product-card template from library, separately select fixture product and opt into retail price, choose EGP, enable owned images, select native column in Layers, map fields, save draft, reload, see exact product name/12.50 EGP/image. No API-authored page.
- Real provider queried rollback fixture WorkspaceFile metadata; browser verified 600px natural image width. Raster fixture generated locally and served locally, no storage charge/upload.
- Desktop and mobile-device390px inspected, no horizontal overflow. One item is one full-width native card, not a finished storefront grid design.
- Actual API negatives: stale token, string boolean, missing currency, duplicate product IDs, unknown policy field, invalid alternate-language card source rejected; policy/page unchanged.
- Every integration test used outer transaction rollback. Exact pre-test settings and page tree/titles/published/status restored; temporary product absent. Credential file removed.

## Still unverified and unfinished

This is not hosted acceptance. Isolated-branch source checkpoint is being completed; no new deployment. Current hosted site retains the preceding name/profile composition checkpoint. Need source upload/readback checkpoint, test packaging and canonical ERP/Studio checks with rollback plan, hosted name/price proof, and a supported hosted media fixture or existing tenant-owned asset without unapproved spending.

Actual-router regression additionally verified generic-settings GET omits the key, direct/nested bypass PUT422, composite core scalar plus typed card preview200, and unauthenticated settings/preview401. Further regression should cover wrong tenant/product/file/MIME via integration, inactive module, permission-denied roles, and concurrent policy updates. Existing provider tests cover tenant/module/media query shapes, but do not replace all these API exercises.

Discovery currently exposes existing scalar/name collections only. Card UI has a fixed reviewed inventory capability; do not describe generic arbitrary module-card discovery as complete. SDK Python manifest mirrors backend; no separate public SDK typed media helpers shipped yet.

Limitations: one card template, no heading-repeat mixing, direct targets only, no public dynamic route/cache, cart/orders/checkout, upload control or signed-in shopper resources. No allwirya parity claim. The data scope remains explicit, default-empty and internal ERP modules remain private.


## Hosted follow-up, 06:52 Cairo

The name plus price subset passed on the isolated canonical test site https://mizan-studio-feature-test.vercel.app/ . Deployment dpl_GFbMUYD57gB9GBARvnn8pksBSzg6 was built from application checkpoint 9b92e8213153ab50b0e223823362b551563d7905. Protected candidate Studio/ERP HTML and all nine referenced JS/CSS files were checked before test canonical promotion. Immediate normal ERP login and settled products body passed.

Normal owner UI added the card template, selected the fixture product through separate card policy, opted into retail display price and explicitly chose EGP. Column targets were mapped through Layers/inspector, draft saved and fully reloaded. Product name and exact 12.50 EGP displayed. Mobile device mode at 390px passed no horizontal overflow. Public dynamic publish stayed409. Page/policy authoring was UI-only; fixture provisioning and cleanup were outside UI. Compare-before-restore verified exact original policy, page tree, titles, published tree and status; the temporary product was deleted and absence checked. Credential files removed.

Hosted image consent stayed OFF. The test tenant has zero existing product-image metadata and zero product image URLs, checked live. No other tenant media was borrowed, no private file exposed, no paid upload made. Hosted owned-image storage/delivery remains UNVERIFIED. Local metadata plus loading proof above does not remove this caveat.

### Additional rollback and permission checks

Real database transaction checks refused missing file metadata, wrong product owner, wrong kind, SVG MIME, URL mismatch and wrong tenant URL even with a matching file record. Exact tenant/product/kind/URL/raster metadata was accepted; inactive product returned no row; dedicated settings refused inactive inventory422. Outer transaction rolled back, temporary product and file rows were confirmed absent. No storage upload.

Actual FastAPI route dependencies were tested with injected identity and no DB: no grants, site.manage only and inventory only each got403 for card settings GET/PUT. Inventory-only preview got403. This checks the real permission dependencies, not a fresh persisted-user login. Existing hosted test used the ordinary authenticated owner.

This follow-up supersedes the earlier no-deployment statement for the name/price subset only. It does not change any unfinished-public-runtime, media, template or commerce boundary.

## Repeated-copy editing follow-up, local only

Canvas selection originally recognized stored node IDs only. Repeated cards have generated IDs, so the accepted hosted path used Layers to select the template. A selection-only map now derives rendered-copy IDs to original template IDs only after exact projection validation. Clicking a rendered name selects its template heading; layout changes apply to every repeated copy. Stored IDs and backend contract do not change. Dragging generated copies is intentionally disabled, use Layers to move the template.

Two local mapping tests cover all fields on two actual Python-generated card copies, optional/empty results, source unchanged and unverified projection refusal. Ordinary UI test with two products clicked the second rendered heading, changed native heading level, saw both copies update, saved and fully reloaded with both levels retained. Desktop and mobile stacked layout inspected; exact rollback restoration verified. This editing change is LOCAL ONLY pending isolated source checkpoint and hosted proof. Current hosted price-card checkpoint remains valid through Layers.
