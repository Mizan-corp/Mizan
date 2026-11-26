# Products and Help Desk are separate domains

Status: domain clarification and source assessment, 24 November 2026. No Help Desk implementation or visitor effects in this checkpoint.

## User requirement

The user's 07:35 Cairo clarification distinguishes services (Help Desk) from products. Apply this distinction to domain models, builder source discovery, navigation, UI labels and acceptance tests. A service description block is presentation only. It is not a Help Desk record, request form or tracking workflow. Inventory product cards must not stand in for Help Desk services or tickets.

## Existing source assessment

- Inventory Product is the existing product domain. Its typed product metadata does not establish a Help Desk workflow. Selected product names/prices and optional owned media remain under the inventory website policy and its independently selected section subsets.
- The existing module whose ID is services is named Professional Services. Its manifest and models describe consulting engagements, project retainers, timesheets and statutory deadlines. The services activity is a legacy alias for consulting. Do not repurpose this module by name alone.
- The existing maintenance field_service domain contains internal work orders, technicians, van stock and equipment history. Work orders include client names/phones/addresses, issue descriptions, assigned technicians and completion notes. These are private operational records, not a reviewed visitor Help Desk source.
- Feature-repository code searches for helpdesk and help desk returned no indexed results. Local source inspection also found no matching dedicated ticket contract. Search absence is not proof that no such contract exists elsewhere or on another branch. Verify the owning activity/module and canonical branch before implementing one.

Inspected paths:
- system/core/backend/app/activities/general/modules/inventory/models/product.py
- system/core/backend/app/activities/services/{activity.json,seed.py}
- system/core/backend/app/activities/consulting/modules/services/{manifest.json,models.py}
- system/core/backend/app/activities/maintenance/{activity.json,modules/field_service/manifest.json,modules/field_service/models.py}
- system/erp/frontend/src/activities/consulting/modules/services/ServicesConsultingPage.tsx
- system/erp/frontend/src/activities/maintenance/modules/field_service/FieldServicePage.tsx

## Required separation

| Concern | Products | Help Desk |
|---|---|---|
| Meaning | Merchandise and catalog records | Service offerings plus support/repair requests and their workflow |
| Presentation | Reviewed inventory card fields | Separate authored service descriptions, until a reviewed service-offering source exists |
| Private records | Costs, stock, suppliers and internal product metadata | Customer identity/contact, device details, issue, conversations, attachments, technician/internal notes, quote decisions |
| Visitor effects | Cart/order/checkout, not implemented by data bindings | Open request, add information, approve quote, view own request status, each needs a separate reviewed command/ownership contract |
| Public listing | Explicit product selection and field consent | At most explicitly authored/consented offering descriptions, never ticket or customer listings |

A Help Desk service offering, a customer ticket and an inventory product are three different concepts. Whether a repair consumes stock or later creates a sales line does not merge their identities. Relationships between them must be explicit and do not imply cross-domain publication authority.

## Implementation order

1. Confirm or define the dedicated Help Desk owning module and its internal state/permission contract. Reuse an actual matching contract only after its semantics are checked, not a similarly named module.
2. Keep a service offering catalog separate from private tickets. Builder sources must be explicitly registered, typed and default off. Do not expose ticket fields through generic discovery or arbitrary model reflection.
3. Build internal workflow and test permissions/state transitions before visitor commands. A generic website content block cannot count as this acceptance.
4. For visitor requests/tracking, define shopper ownership or an independently reviewed capability, exact minimized fields, idempotency, rate limits/spam controls, retention, notifications and attachment safety. Never authorize access through an ERP ID or predictable work-order reference alone.
5. Integrate public runtime only through the default-disabled activation boundary in visitor-runtime-boundary-proposal.md. Current dynamic publish409 stays in place.

No deployment, public activation, Help Desk write, notification, customer disclosure or commerce transaction follows from this document. Existing service-labelled screenshots prove only editable illustrative content, not a working Help Desk.
