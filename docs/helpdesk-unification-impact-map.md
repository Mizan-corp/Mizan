# Unified Help Desk: impact map and migration boundary

Status: implementation direction approved by24November08:16–08:20user messages; this document is the reversible architecture checkpoint, not completed migration. Current healthy isolated deployment remains unchanged.

## Two independent axes

The module owns its features. Every feature exists in every variation. Variation selects activity-specific terminology, fields and workflow behavior; it does not create, remove or reset features. Feature state survives a variation change. Do not implement a per-variation feature allowlist or treat a feature as a variation.

Dependencies between capabilities or other modules can be explicit and checked uniformly for every variation. Such dependencies cannot be used as a disguised variation gate. A capability needing a scheduling or inventory service must show the real missing dependency, not claim the feature does not exist for this variation. No integration action or paid service is activated automatically by switching a Boolean.

Existing framework observation: workspace activity selects one effective variation per module, with planned variants falling back to standard. Typed module settings currently live independently in mod_settings_<module>. Preserve this separation. New work must not silently change activity or introduce an unrelated variation selector.

## Grounded candidate map

| Existing/planned concern | Evidence | Shared Help Desk portion | Variation-specific or integration boundary |
|---|---|---|---|
| Field service / maintenance | FsmWorkOrder: client/site/equipment/issue/SLA/technician/van/schedule/status/completion. FSM-01,02,05. | Service request, work identity, assignment, status history, authorized private notes. | Field-service wording, equipment/site details and dispatched/on_site/parts_needed/completed behavior. Technician routing and van stock are capabilities/integrations, not variation-only feature availability. |
| Property maintenance | RecMaintenanceTicket: unit link/category/description/reporter/cost/CAM/status. RE-08 explicitly routes tenant complaints to FSM-02 work orders. | Same request/work backbone, no second duplicate support engine. | Property/unit context, lease/tenant identity, open/assigned/in_progress/resolved behavior, CAM cost allocation stays accounting/property integration. |
| Salon service catalog | SalonService: name/category/duration/buffer/base_price/consumable_cost/active. SAL-01. | Reusable offering identity and optional service-catalog feature. | Salon wording/fields; scheduling/rooms, prepaid sessions and commissions are separately configured capabilities or linked engines. Private beauty formulas and sensitivity notes are not catalog content. |
| Consulting/professional services | ConsultingEngagement,Timesheet,StatutoryDeadline; CON requirements. | Reusable client service intake/work/deliverable references where lifecycle matches. | Retainers, hourly/milestone billing, time approval and statutory filing semantics remain explicit, not renamed tickets or erased into one status enum. |
| Hotel maintenance | HOT-06 specifies engineering requests that make rooms out of service. | Maintenance request/work link. | PMS owns room availability and housekeeping; Help Desk completion cannot silently mark a room sellable. Implementation presence must be checked separately from requirement. |
| Equipment/asset maintenance | HLT-09,ENG-03and equipment-maintenance planned requirements. | Maintenance request/work link and equipment references. | Calibration/regulatory evidence, condition readings and clinical/safety access remain protected in their domains. Do not migrate solely because of the word maintenance. |
| Generic support/complaints | New confirmed user direction; no matching general requirement found in reviewed SRS. | Standard Help Desk request/work behavior and optional catalog. | Exact default lifecycle and private customer-access rules still require a written contract before execution. |

False name matches: event/travel admission tickets, kitchen tickets, clinical chief complaints, HSE incidents and logistics incidents are not automatically Help Desk. If they need corrective service work, link an authorized Help Desk request; do not absorb their legal/clinical/accounting identity merely because they have a status or description.

## Module-level feature candidates

Confirmed: service_catalog. Proposed from existing requirements: assignment/dispatch,SLA,equipment_history,scheduling_link,quote_approval,parts_usage,customer_portal,attachments and notification delivery. These are candidates requiring exact contracts, not implemented toggles. They must all remain available in every variation. A feature may be disabled, lack required permissions or need an external engine; variation is not the reason for its absence.

The catalog uses an explicit starting amount/currency for newly authored offerings. Existing SalonService.base_price, consulting hourly_rate/contract_value and inventory retail_price must not be relabeled starting prices automatically. No automatic price or tax conversion is approved. Internal costs and consumable costs never enter website discovery.

## Reversible implementation sequence

1. Add a versioned Help Desk contract and source-to-common mapping with stable legacy references. Keep source tables, identifiers, routes and current grants intact. Mark incomplete capabilities honestly rather than mount planned stubs as working features.
2. Define independently persisted module feature state. Test all features against every variation and prove variation switches leave feature state unchanged. Default catalog off until the workspace explicitly enables it; preserve service/history rows when disabled.
3. Start one compatible non-destructive slice, preferably property maintenance/FSM request identity because RE-08 explicitly links them. Use compatibility adapters and dual-read comparison before routing legacy screens to common behavior. Do not dual-write without an idempotent reconciliation contract.
4. Keep authorization no broader than source grants. Resolve the least-privilege read/manage boundaries before common endpoints; tenant matching alone is insufficient. A shared route must not expose a property reporter to an unrelated technician or a salon treatment history to a general support agent.
5. Verify source row counts/identities, money precision, attachments, assignment, status transitions, audit history and unchanged existing screens before any migration. No destructive migration or legacy deletion is part of this checkpoint.
6. Integrate the optional catalog into Settings and then reviewed builder projection. Public runtime, customer request submission, quote approval and payment remain separately tested effect boundaries.

## Concrete conflicts to handle, not hide

- Existing candidates use different status sets and sometimes Float money/string dates. Unification requires explicit conversion and retained originals, not silent coercion.
- Several source routers use sign-in/module checks rather than the future common fine-grained read/manage contract. Do not copy that broad access into a new shared endpoint.
- Current activity-specific variant resolution supplies one variation per module. Optional features cannot be implemented by adding/removing variation files or changing activity defaults. Feature state must be independent and survive changes.
- Existing module activation/licensing IDs cannot be aliased wholesale to Help Desk while unrelated consulting,property or salon functions still belong to those modules.

## Acceptance boundary

A design document or empty registered module is not a working Help Desk. Completion needs actual internal role-tested request/offering flows, preserved legacy data and routes, all-variation feature-state tests and visual acceptance. No public access, booking, payment, notification or customer-data disclosure follows from this architecture direction alone.

## Registration confirmation and current code checkpoint

At08:20the user confirmed registering Help Desk under General Modules, updating documentation and Business Activities, and wiring consolidated activities to their variation. The earlier clarification hold is lifted. Preserve the shared Help Desk owner plus independent module-level features. Registering an empty module must not be presented as usable functionality.

Local helpdesk_contract.py implements only strict module-level catalog feature state plus explicit, read-only property/FSM source summaries. No endpoints, queries, database tables, role grants or activity mappings are changed by this file. Source adapters require an already-authorized row and explicit matching tenant; tenant equality does not establish permission. Tests cover strict booleans, partial updates, source identity/status retention, tenant mismatch, allowlist privacy, malformed input and unsupported sources. No persistence/variation-switch integration claim follows from these pure-function tests.

SRS conflict: the industry-services phase identifies HOT-06 as room maintenance; compiled SRS uses HOT-06 for hotel POS integration. Keep phase source qualification rather than assert that code is globally unique. Live assets/models.py is a placeholder; hotel_pms/models.py re-exports room/reservation models and does not itself establish maintenance implementation.

Next: implement the module in the complete isolated source tree, explicit feature metadata/settings, minimum internal offering/request contracts and registered variations; add permissions and actual data/API/UI acceptance before rewiring legacy routes. Adapter summaries alone are not migration or completed unification.

## Local module source,08:24

Added planned helpdesk manifest under general/modules, standard variation, tenant-scoped Numeric(14,2) offering model, strict create/archive schemas, module/permission/feature-gated private list/create/archive source and central audit writes. Draft additive RLS migration is not wired or executed. Manifest remains planned, so registry does not offer/mount incomplete work. Supported currencies initially restricted to EGP,USD,EUR,GBP,SAR,AED,QAR, all handled at two decimal places; three-decimal currencies are intentionally rejected until precision support is added. Schema checks passed for trimming, precision, nonnegative/finite amounts, unknown fields, unsupported currency and strict archive Boolean. Source compiles. No real endpoint/database/UI acceptance yet.

Next exact step: copy planned module into complete /tmp/mizan-collection-api test source, import it directly in an isolated transaction harness (without setting manifest active), apply draft table inside an outer rollback, wire actual source router and registry in harness, test real role/session permissions, disabled409, enabled catalog create/list/archive, cashier403, cross-tenant404, exact original settings/fixture rollback. Then UI and actual registration can follow. Do not ship planned stubs or bulk-run existing migration suite.

## Actual internal catalog acceptance,08:33

Local actual JWT sessions/effective custom roles passed anonymous401,no-grant403,read-only create/archive403,disabled409,enabled create201/read200,invalid amount/currency/tenant injection422,archive/restore,disable/re-enable preserving records,module inactive403. A real second tenant row was invisible through ORM and raw RLS and archive returned404. Central audit service had obsolete action/changes/note column names; the new module instead inserts through declared AuditLog(action_type/details/reason), leaving shared service/schema unchanged. Two expected audit events verified.

New React catalog UI passed actual create/save/fullreload/archive/fullreload/restore, explicit starting-price and selected currency,390px no overflow and no page errors. Desktop/mobile screenshots visually inspected for labels/cards/form/stacking. TypeScript and dedicated UI build pass. Every temporary table/tenant/user/role/setting/activation was enclosed in outer rollback and verified absent or exactly restored. These are local isolated results, not hosted availability.

Manifest still planned; migration not wired or retained in database. UI not in normal ERP navigation yet. No variation/activity remapping or request-workflow completion claim. Next run should add normal route/module registration, tracked atomic migration and variants without losing independent feature state, then repeat full ERP UI acceptance before isolated deployment. Existing shared migration runner marks some failures applied; do not add this table through a silent-best-effort path. First resolve an atomic, verified additive step. No destructive/source data migration.
