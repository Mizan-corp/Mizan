# Shared core website reflection scope

Working inventory, 24 November 2026. Implementation incomplete, local only.

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
