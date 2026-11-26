# Shared core website reflection scope

Working inventory, 24 November 2026. Implementation incomplete. Later hosted follow-ups below supersede the earlier local-only checkpoints.

The actual general activity inherits core, contacts, inventory, operations, sales, purchases, finance, pos and hr. The manifest is_core flag is not equivalent to this list and is never a publication rule. Platform engines such as site/themes/i18n/community support the builder but do not all own visitor data.

## Module-owned scope

| Module | Actual source / visitor-facing role | Safe implementation boundary |
|---|---|---|
| core/settings | StoreSetting and tenant identity, existing invoice/business settings | Separate explicit website business profile, default absent. Never fall back to legal/invoice name, address, phone or tax number. |
| inventory | Product, Category, Subcategory, ProductImage, ProductCollection | Opt-in per record, independent from is_active. Start reviewed text projection from selected active products/categories. Never costs, wholesale, barcodes, stock balances, shelves, warehouses or extra JSON. Money/media need typed runtime support. |
| contacts | Customer and Supplier, balances/credit/contact details | No public listing. Future signed-in own-customer profile only, after shopper identity mapping exists. No ERP-user identity shortcut. |
| sales | Sale/line/payment, quotations and invoices | Future signed-in own-order/invoice view after shopper identity mapping. No public invoice or order tracking, no writes in data binding. |
| purchases | Purchase/receipt/return/supplier-price records | Internal only. No visitor projection identified. Supplier portal is separate authenticated planned work. |
| finance/accounting | Safes, wallets, ledger, expenses, periods | Internal only. Payment-method display belongs to explicit commerce configuration, never wallet rows/account details. |
| pos | Cashier shifts/drawer transactions | Internal only. Website checkout is not POS drawer reflection. |
| hr | Employee/payroll/attendance, including national ID/salary | No public employee rows. A separately authored opt-in team directory would require its own publication model, not payroll projection. |
| operations | Stock-transfer and request documents | Internal only. Public shipping status needs separate customer-owned commerce model. |
| reporting | Internal financial/stock/customer reports | Internal only. No public counters or summaries inferred. |
| site | Saved brand/navigation/footer and native published pages | Existing scalar brand plus local navigation repeat. Publication state remains explicit. |
| themes/i18n | Theme packages and language metadata | Builder/runtime presentation capability, not arbitrary DB projection. |
| community | ExtRecord and installed manifests | Optional developer-owned reviewed contracts only. No automatic records/fields exposure. |

Pricing/scheduling/documents/loyalty/customer_portal/supplier_portal and other general-module skeletons have no actual model implementation at the current checkpoint. Do not manufacture live providers from names. Legacy storefront is retired/planned and is not a safe shortcut.

## Publication policy

Module-local explicit website opt-in settings and reviewed contracts cover core business profile and inventory catalog text. New settings default off/empty. No existing record becomes visible by deploying support. No public resolver or commerce transaction is authorized by this work. Owner choices about which records and fields to publish occur through explicit controls, not migration defaults. Keep price/media, protected shopper data and effect-bearing commands separate from text binding.

## Local implementation checkpoint

Core module owns profile provider, validation and website settings endpoint under platform/core/storefront. Only display_name/tagline authored explicitly for website use are supplied. Inventory owns products/categories text provider and explicit bounded UUID selection under activities/general/modules/inventory/storefront. Product names above the text runtime bound fail closed rather than truncate. Provider query explicitly selects id/name only and checks tenant/active/allowlist. Category selection is independent; selecting a product never implicitly selects its category. StoreSetting keys default absent, not populated from any existing record. The generic settings route refuses reserved publication keys and omits them from its general read response, so settings-only access cannot bypass dedicated dual-permission controls.

Local API discovery and Studio Data panel expose the reviewed providers plus explicit settings, and an experimental heading repeat template is preserved in the native page format, with byte-identical SDK/platform validation. Public dynamic publish remains409. Current UI supports one template, no mixed scalar bindings, text only. Inventory choices are bounded to200with an explicit truncation notice; selections outside shown choices are retained. This is not general pagination or full-catalog browsing.

Actual normal owner local API/UI acceptance selected a temporary product, saved explicit website selection, bound heading template, saved/reloaded native draft and showed the provider value. Original static content remained. Explicit profile and selection persisted through reload. All application commits were enclosed by an outer transaction that was rolled back at shutdown. Exact original settings and page tree/titles/status were verified after rollback; temporary product verified absent. No fixture commit and no ERP/commerce transaction. Screenshots are local real UI/API/DB, not hosted or committed persistence proof. Separate populated provider rollback test excludes selected inactive and unselected active rows and verifies exact projection.

105frontend tests pass/1skip, TS/build pass;20collection/repeat tests and6provider tests pass. Eight authorization dependency checks deny callers missing either site.manage or module/settings permission. Two generic-settings bypass checks return422. These are override checks, not a real alternate user login.

Actual API negative checks cover stale profile/catalog tokens (409) and unknown, duplicate, malformed, oversized, private-extra and tenant-override input (422), with unchanged state after refusal. Mocked desktop/mobile UI checks cover dirty close cancellation, conflict freeze, explicit discard/reload and 503 retaining the edit without blind retry. These mocked failure checks are not hosted integration proof.

Remaining before hosted milestone: complete source checkpoint/readback/build, isolated deployment and actual hosted save/reload/restoration. No claim that all core, protected customer records, typed media/money, public rendering, cart or checkout is done.

## Hosted text milestone and local composition continuation

The 36-file checkpoint b9bc6fbf2709cf266907ccf867a87158ee2c90ea was pinned-read, rebuilt and deployed to the isolated test project. Normal-owner hosted acceptance exercised explicit profile/catalog controls, product repeat selection, draft save/reload and publish409. Exact original raw settings and page tree/titles/published/status were restored and the temporary product removed. ERP sign-in and products body were checked after correcting the deployment build to VITE_BASE=/erp/ with VITE_API_URL=/api. Corrected deployment: dpl_8HSBBpzwVAzp9KGUi9Ww8YxYQkqt. This is not production, all-core completion or public dynamic publishing.

The next local composition adapter allows scalar profile headings and one repeated catalog heading on the same page. It validates both families and every declared language before provider reads, uses bounded native expansion, restores only scalar sibling declarations, then resolves scalar text. Same-node conflicts and multiple repeats remain refused. Frontend exact projection checks and native validator support this combination. Module settings dirty state is now reflected in the page status label. No new fields, record exposure, public endpoint or commands are added.

Local actual normal-owner API/UI acceptance binds both headings, saves and reloads together with static text retained. The second static heading was prepared through the API, so this is not UI-only page construction proof. All writes were inside an outer rollback transaction with exact restoration. Negative API checks refuse inactive-language private fields, same-node conflict, a second repeat and aggregate bounds at both preview and save, with exact stored state unchanged. Unit checks also cover failure without partial/static fallback. This continuation still needs exact branch checkpoint/readback and hosted acceptance before being described as deployed.


## Current hosted composition checkpoint, 07:30 Cairo

This follow-up supersedes earlier one-template, text-only and local-only statements for the narrowly tested subset, not for the whole module inventory. See native-product-card-local-acceptance.md for source and acceptance details.

Canonical isolated preview: https://mizan-studio-feature-test.vercel.app/ . Application checkpoint995af1dde7f9e86f843806a810b5fa59db00512e, deployment dpl_8ia347mhvM4SHfjRT6Yzqe7Lmvst. Explicit core profile scalar headings, selected active inventory name/category headings and native editable product cards exist. Cards expose names plus independent default-off retail display price and tenant/product-owned raster media consent. Money is exact typed decimal and explicit currency label only, no conversion or tax inference. Hosted name/price and repeated-copy editing passed; owned-image loading passed locally only, hosted media remains unverified.

Cards now support one to four independent native rows and optional per-language explicit product subsets up to six records. Subsets only narrow saved card publication consent; removed consent blocks stale subsets. Aggregate planned card slots at most12 and page nodes at most500, all-language preflight before provider reads. Existing plans without explicit subsets preserve legacy first-consented behavior. Heading-repeat mixing, arbitrary module cards and nested bindings remain refused. UI lists only currently consented products among the bounded200inventory choices; this is not pagination, category-query filtering, sorting or general product browsing.

Hosted owner API session with UI-only authoring built two independently selected card sections with editable illustrative services and explicitly non-sending contact content, saved/full reloaded, and edited only the second card template through its rendered copy. Exact original page and policy restored, both fixtures removed and absence checked. Desktop/mobile and authenticated ERP body inspected. Frontend203pass/1skip plus typecheck/build; backend15runtime/provider checks and separate real-DB rollback negatives passed. These counts are scoped, not all-backend-suite acceptance.

Still NOT READY for the user's no-code allwirya recreation criterion: complete selectable multi-page themes, matching visual design, full catalog browsing, public dynamic runtime/cache/security, shopper identity, repair tracking, quote approval, part enquiries, orders/cart/checkout and actual form delivery remain unfinished. Internal/protected module exclusions in the table above remain unchanged. Do not expose private ERP data to fill these gaps or remove publication guards. Service content tested here is illustrative copy, not a claim that those business modules or workflows exist.
