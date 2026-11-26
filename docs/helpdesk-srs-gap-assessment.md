# Help Desk and optional service catalog: SRS assessment

Status: research and proposal only,24November2026. No new module, catalog schema, ticket workflow, public command or permission grant implemented by this assessment.

The current request describes services as offerings with starting prices, distinct from inventory products. The catalog is an optional feature inside Help Desk, enabled or disabled from that module's settings. A ticket may track work, but is not the service offering. Disabling a catalog must not delete prior services or requests. Final-price approval, booking, payment and fulfillment rules remain unspecified.

## Reviewed sources

Read current master7046f4468c803bc8c2693282bc24b0e2b3e1febc through repository reads: docs/srs/00_MASTER_INDEX.md,01_SHARED_ERP_CORE_SRS.md and all six industry phase specifications02through07. Also read docs/developer/mizan/srs/SRS-Mizan-v1.0.md and docs/decisions/ADR-015-website-builder-and-storefront.md. Searches supplement these reads; search absence alone is not proof of absence.

## Findings

- SAL-01 specifies a salon Service Catalog & Duration Matrix with duration, buffer and price. This is sector-specific and does not define a general Help Desk service offering with a starting-price mode.
- FSM-01 specifies service request/ticket intake: category, priority/SLA and equipment location. FSM-02 specifies work-order generation and dispatch. FSM-05 specifies SLA monitoring. These cover field service operations, not the optional catalog described in the current request.
- CRM-02 includes ticket interactions in customer communication history. It does not own a ticket or service catalog contract.
- The master index lists30industry packages and15shared engines, without a dedicated general Help Desk domain in the reviewed taxonomy.
- ADR-015 plans a website builder and commerce catalog. It does not establish this Help Desk service-offering catalog or permission to publish internal tickets.

The exact requested general feature is an uncovered specification gap in the reviewed sources. This does not prove it was never discussed, or that no other branch or external document contains it. Specifications and implementation must be checked separately. Current scoped code assessment has not found a matching owner; similarly named consulting services and internal field-service work orders are not substitutes.

## Proposed specification addition, not an approved contract

Record a dedicated Help Desk boundary and its optional catalog capability. Define service identity, authored name/description, explicit starting amount/currency and the fact that the amount is not a final quote. Keep private customer requests, messages, attachments and internal work notes outside catalog projection. Define independent read/manage permissions and effective-role settings access before implementation. Feature disabling should gate new catalog discovery/use without deleting historical records. Existing owner account controls remain separate from ERP role-authorized module controls.

Before execution, settle the actual owning module contract and approval rules for final price/work requests. Public request submission, customer tracking, booking and payment each require separate security and business acceptance. No existing product price should silently become a starting price, and untracked inventory is not a Help Desk identity.
