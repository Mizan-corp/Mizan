# Proposed Help Desk service catalog contract

Status: proposal for review, not implemented.24November2026.

## Confirmed current requirements

- Inventory products and Help Desk services are distinct domains.
- A service is an offering with a name/description and price that starts at an amount. A service is not simply a support ticket.
- Catalog is an enable/disable feature inside the Help Desk owner's module settings, not a standalone catalog module.
- Settings should list modules and show the selected module's settings, features/options and effective variation.
- Owner account settings are not identical to settings that other roles may see or change. Server authorization must enforce the boundary.

These requirements now establish one unified Help Desk owner for genuinely similar service request/work handling, with activity variations and module-level features as independent axes. Every feature exists in every variation; changing variation must not reset feature state. See helpdesk-unification-impact-map.md. Final-price calculation, customer commitments, payment and exact fulfillment contracts remain separate unresolved scopes.

## Proposed minimal offering record

A tenant-scoped stable identifier, authored name/description, active/archive state, explicit starting amount and ISO currency. The starting amount is a presentation floor/reference, never an automatically payable final quote. Use fixed-precision numeric storage, validate nonnegative amounts and supported currency, and show an explicit starting-price label. Do not infer meaning from inventory stock_status, product_type or retail_price.

Images, categories, duration estimates, fixed-price mode and variations are optional additions that need a reviewed contract. Do not include them merely because a similar sector model has them.

## Proposed optional catalog feature

Default disabled for an existing workspace unless an existing source-grounded setting says otherwise. Persist through the established typed partial-update module settings path, with an explicit Boolean. Turning off gates new catalog listing/selection; it does not delete offerings, requests, accounting records or their history. It must not uninstall Help Desk. Preserve historical references and show an honest disabled state to authorized operators.

A feature gate does not imply a public website listing. Private ERP catalog visibility and website publication consent are separate. Builder discovery, preview and execution must re-check the feature, module activation and current permissions. Revocation should block further projection rather than reuse a stale generated result. Public runtime still needs its separately reviewed activation boundary.

## Proposed permissions and audiences

Keep offering read, offering manage and module-settings administration separate concepts. Map them to actual existing declared grants only after the owning contract is recovered or approved. Do not grant every non-owner the same access. Effective acting role controls access; an owner flag or role name is not a substitute. Standard manager/custom settings access is preserved by the settings refactor, not expanded into future ticket access.

Catalog projection should contain only explicitly allowed offering fields. Never discover private ticket/customer/device/chat/attachment/technician fields through generic model reflection. Quote totals, deposits, tax and customer commitments must not be inferred from the starting amount.

## Remaining execution boundaries

1. Implement the unified Help Desk owner through a versioned common contract and reversible compatibility adapters, preserving unrelated consulting/property/salon functions and existing grants. General-module registration, documentation updates and Business Activities rewiring were confirmed by the user at08:20. Implement them only with working variation adapters, explicit permissions and compatibility tests, not as empty catalog entries.
2. Define whether a visitor selects an offering into an enquiry/request or a committed order, and who calculates and approves final price. A starting price alone does not answer that.
3. Define disable behavior for in-progress requests and any published service pages. Preserve history; decide explicitly whether existing clients can continue private tracking.

Before visitor requests: independent identity/ownership, idempotency, rate limiting, spam controls, attachment safety, retention and notifications. Before booking/payment: wallet-bearing terms, cancellation and total-cost rules. These are not delivered by static blocks or a toggle.

## Acceptance targets after scope approval

Authorized role creates an offering with explicit currency/starting amount. Unauthorized and cross-tenant reads/writes fail. Optional feature survives reload; disable blocks discovery without deleting history; re-enable restores eligible records. Generic settings cannot bypass validation. Owner-only fields remain unavailable to ordinary ERP roles. Builder preview uses only reviewed offering projection and re-checks revocation; published/runtime behavior is tested separately. Visual desktop/mobile checks accompany functional proof.
