# Current state, 24 November 2026 at11:34

The bounded non-posting execution worksheet is now hosted at https://mizan-studio-feature-test.vercel.app/, source ba722ca8a5bb39e70bd91dc2baca09cdadb51ad8. Four independent default-off Help Desk features are deployed. Hosted real-JWT/API and full-ERP UI acceptance/cleanup passed; see helpdesk-current-status.md for current evidence. Earlier local-only statements below are dated implementation history. No stock/financial posting or complete business-flow claim.

# Unified service execution and cost trace

24 November 2026. Corrected design after the user's site-work/resource concern and whole-business instruction. This supersedes the dispatch-only proposal as the next implementation direction. No claim of completed workflow.

## One business record, distinct responsibilities

The operator works on one request and its execution worksheet. Existing property/FSM native identities remain linked context, not duplicate forms or two independently drifting jobs. An offering is what can be sold. A request is the client's need. Actual work, technician effort, materials and evidence explain fulfillment. Cost is the business's resource basis; a selling rate or quote is a different commercial decision. Invoice, payment and journal each remain separate identities and approvals.

A practical worksheet must retain measured inputs even when no rate exists yet. Unknown cost is unknown, not zero or a reason to discard the work. Operational completion and costing completeness are separate states. Installed/consumed material and a returned material are separate events. Returning material does not itself prove a stock receipt, customer refund or reversal of installation.

## Source-grounded facts

- FSM work contains issue/site/technician-name/schedule/status/completion notes, but no structured execution-time or material-use ledger.
- FSM van consumption only decreases an integer quantity, with no work link, stock movement or cost snapshot. Its existing endpoint is not a safe common costing adapter and is not reused.
- Central inventory records Decimal product/warehouse movements and maintained balances. apply_movement owns availability checks, weighted-average valuation and inventory hooks. There is no service-consumption movement kind yet; do not disguise service consumption as a sale, damage or adjustment merely to get a decrement.
- Inventory's existing cost-read scope is inventory/purchases/reports, not ordinary operations. Technician access to work does not imply access to labor or stock cost.
- Accounting posting owns balanced entries, idempotency, periods and reversals. A worksheet must never create a second direct journal writer.
- Technician has no hourly labor-cost rate. Consulting timesheet rate is not a maintenance wage; employee base salary is not an authorized hourly allocation formula. Property Float cost/CAM is not the common cost ledger.

Sources inspected: current deployed c2fe4f1 source, field_service router/models, inventory stock model/service and product cost visibility, accounting posting service, property ticket model/router/UI, consulting timesheet and employee source models. SRS coverage: FSM-01/02/04/06/09, RE-08, INV-02/03/04, FIN-01/05/06/11/13/15.

## First bounded implementation

Private non-posting actuals contract and worksheet persistence/UI, not merely another dispatch action.

- Exact source request/native work ID, revision and operation ID; stable technician/product/warehouse identities validated against the acting tenant and source permissions.
- Site work description and dated measured labor/task/material lines. Labor records hours, not an inferred wage. Material records explicit unit, quantity and installed/consumed/returned meaning.
- Optional separate cost and selling snapshots, each with currency, basis and provenance. Missing snapshots remain explicit. Stored snapshot estimates are not movement-time posted valuation or final customer charges.
- Decimal arithmetic; currencies are never added together or converted implicitly. Known subtotals plus missing-rate counts, not a misleading complete total or profit.
- Corrections retain the original, link to the prior line and exclude superseded lines from the current measurement. No negative-quantity correction shortcut. Resource identity cannot silently change via a correction.
- Idempotent save and optimistic revision conflict, with transaction/role/tenant/privacy tests before mounting a route. A non-cost reader receives no hidden cost values or aggregates.
- Explicit stock-unposted, accounting-unposted and invoice-not-created state. No existing completion route is silently blocked or redefined by a partial worksheet implementation.

## Later effects requiring actual contracts

Reuse existing central WAC and posting services, rather than asking the owner to redesign them. Before service stock issue/return: define real issue/reversal movement identity, warehouse access, reservation/negative-stock/batch/serial handling and transaction boundary. Before labor allocation: obtain configured authorized rates/basis, never guess from salary or consulting prices. Before customer charge: configured fixed/time-and-materials/contract terms, tax and approval. Before close-blocking: define which operational or cost approvals are required by this business. These remain explicit unresolved policies, not hidden defaults.

## Current acceptance level

Local actuals_contract.py and nine contract tests pass strict quantities, stable references, independent cost/selling bases, currency-separated Decimal subtotals, unknown-vs-zero, returns separation, correction retention, source-line identity and projection privacy. No persistence table, API, UI, stock, financial posting or hosted change is claimed by these tests. Full Help Desk and full-business fulfillment remain incomplete.

## Local append-only persistence primitive, 10:40

Local model and unmounted actuals.py now store revisioned full worksheet snapshots, scoped source/native IDs and operation fingerprint. Exact same-user retry replays; expected revision guards stale saves. Existing line history cannot be removed or rewritten. New linked corrections retain originals. Hidden cost/selling snapshots survive an operations-only read/append without being disclosed or erased. Source/technician/product/warehouse references are explicitly tenant filtered. Source work and technician state are unchanged.

Actual PostgreSQL outer-transaction test passed initial save, replay, second correction revision, stale409, unauthorized snapshot403, redacted projection plus append preserving hidden old cost, explicit missing cost on new actual, and unchanged native work/technician. New table and fixture source rows were rolled back, table absence verified. No persistent migration. This does not establish RLS, mounted JWT route/feature gates, warehouse-subscope access, concurrent transaction behavior, source deletion behavior, UI or hosted acceptance. Those remain mandatory before exposure. This code must not be mounted merely because the primitive tests pass.

## Local route/concurrency gate, 10:43

Mounted only in the local test source: dedicated work_actuals Boolean, default off in all five variations; explicit work-record, cost-snapshot and selling-snapshot grants. Cost scope additionally requires existing inventory/purchases/reports visibility. Actual JWT route tests passed anonymous401, each missing common/source/record grant403, default/disabled409, strict422, save/replay/read, authorized cost subtotal versus work-only redaction, missing source404, and saved feature state across all variations. Warehouse-specific access is checked on material writes and worksheet reads, active same-tenant product/location validation, base-unit match without implicit conversion. Tests cover missing resource404, warehouse403 and unit422.

Independent PostgreSQL transactions prove exact duplicate waits/replays and changed command conflicts409, with exactly one revision. Forced RLS test under mizan_app hides another tenant's row. Uniquely named disposable schema cleanup verified. No persistent migration or new table remains. The current deployed source c2fe4f1 remains at three features; the fourth feature is local only. No ERP worksheet UI, atomic tracked migration, hosted acceptance, stock/financial posting or business readiness claim yet.

## Local ERP worksheet, 10:51

Actual JWT full ERP UI passed recording1.500hours against selected stable technician and2installed pieces against selected product/base unit and an explicitly allowed warehouse, save/fullreload and unchanged native parts_needed state. Current resource labels are looked up for authorized display. Read-only role sees worksheet without entry form; unknown rates and unposted stock/accounting/invoice state remain explicit. Desktop/mobile390, configured theme, no horizontal overflow or page errors. Screenshots visually inspected. Full fixture table/users/source/products/warehouse/membership/settings rolled back, absence/restoration verified.

Not yet accepted for deployment: historical resource labels currently use live lookup, no retained label snapshot; rate/correction entry UI absent (API primitives only); no final atomic tracked migration; no final full regression, foreign-tenant reference/failure rollback matrix or hosted acceptance. Current hosted source remains c2fe4f1 and three optional features. Fourth feature work_actuals is local only. Do not copy local models/router into a new candidate until all new table/migration gates pass.

## Local readiness followthrough, 11:07

Rate/correction UI now tested with explicit entered20EGP hourly cost and45EGP proposed selling basis,1.5h original retained plus2h correction. Known40EGP cost and90EGP proposed selling subtotals remain incomplete for the uncosted material, and are not posted costs/final charges. Historical technician/product/location labels are now stored server-side per revision and survive source rename. Foreign-source404 and simulated postflush rollback pass. Existing catalog/completion/history ERP regression passes. Clean viewport screenshot shows corrected line and both subtotals unobscured by fixed header.

Atomic additive migration rehearsal passes forcedRLS and read/append grants. A table-local trigger rejects UPDATE/DELETE/TRUNCATE as mizan_app even after the shared grant helper's wide grants are simulated. Shared helper is unchanged. Unknown pre-existing table fails closed. All migration/source fixtures rolled back. Migration registration v111_helpdesk_execution_actuals is local only, not applied persistently. Remaining: exact source checkpoint, final pinned build, isolated hosted migration/app acceptance and bounded cleanup. No hosted fourth-feature claim until that finishes.
