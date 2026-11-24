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
