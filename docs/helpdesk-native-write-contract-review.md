# Native work writes: consolidation review

Current implementation: see [Help Desk current status](helpdesk-current-status.md). Earlier sections below are dated local/source review stages.

Status: source review, not implemented shared writes. No production or commerce effects.

## Current source behavior

Reviewed complete isolated source: app/activities/maintenance/modules/field_service/router.py, models.py; app/activities/property/modules/real_estate/router.py, models.py; framework/helpdesk_contract.py.

| Concern | FSM | Property maintenance |
|---|---|---|
| Create | Generates WO-FSM reference, starts dispatched. Requires client/site/equipment/SLA/technician/van/date text. | Caller supplies reference, unit, description and reporter. Includes Float cost and CAM flag, accepts caller status. |
| Status | Arbitrary status string, optional completion note. | No standalone ticket update/status endpoint in reviewed router. |
| Completion effects | Every completed submission increments technician jobs_completed_today and makes technician available. Replay is not idempotent. Technician matched by name, not stable FK. | No completion effect present in reviewed router. |
| Concurrency | No row lock/version precondition in status endpoint. | No ticket mutation contract beyond create. |
| History | No status-history/audit write in reviewed create/status functions. | No status-history/audit write in reviewed create function. |
| Tenant boundary | Explicit tenant predicate on order and technician lookup. | Ticket create uses supplied unit_id without explicit same-tenant unit lookup in reviewed function. |

Existing source routes use authenticated tenant context. New common reads additionally require common read and operations grants and both module activation checks. Do not infer a manage grant from operations.

## Non-destructive implementation requirements

1. Keep read adapters separate from writable lifecycle. Do not call existing FSM completion endpoint as a replayable generic transition.
2. A common write needs stable source identity, expected native status or version, a unique operation ID, row lock and one transaction for source write plus audit/result.
3. FSM completion must apply technician counter/availability at most once per permitted transition. Existing legacy endpoint cannot be silently replaced before parity tests cover its callers.
4. Property creation must verify the unit belongs to the acting tenant before creating a linked work row. Cost/CAM remain private accounting context, not catalog starting price.
5. Preserve native statuses and expose permitted actions from the source contract. No new unified enum may erase legacy states. Existing arbitrary/empty legacy strings need explicit handling, not an invented transition graph.
6. Add an append-only operation/history record before claiming reliable status history. No such common schema is applied by this review.
7. Test concurrent duplicate operation, stale expected state, missing grants, inactive sources, other-tenant reference, transaction failure rollback and repeated completed submission before routing UI writes through a common path.

## Open product boundary

Generic standard request creation/default lifecycle and customer access are not fixed by the source code. Keep them unimplemented rather than choose a customer-facing commitment or payment meaning from the word Help Desk. The optional internal offering catalog already has its own explicit starting-price contract.

## Coverage warning

Current strict source summary rejects blank native reference/description/status. Legacy create schemas accept arbitrary strings. The local read adapter now emits invalid_source_rows and the UI warns that the list is incomplete. Actual malformed-row API and visual tests pass. Do not let one malformed legacy row masquerade as no work.

## Internal FSM completion primitive, local only

completion.py is not imported by any router. It adds a source-specific completion primitive with an expected native state, UUID operation ID, native-row and technician locks, deterministic audit-operation identity, request fingerprint, and same-user exact replay. It preserves native completed status and applies the technician effect once. Notes stay on the source row, not in audit/response. Missing or ambiguous technician fails409 instead of silently dropping or guessing its effect.

Actual isolated transaction tests pass rollback after simulated failure, same-operation replay, changed payload409, stale state409, unknown row404, invalid source ID/status422, missing/ambiguous technician409, one audit and one counter increment. Actual independent PostgreSQL transactions tested the row lock: duplicate operation waits then replays; different operation waits then conflicts409. One counter increment and one audit verified. The uniquely named disposable test schema was removed and absence verified; public source tables/rows were untouched.

Not accepted: no mounted writable route, no effective manage grant/feature UI, no completion screen, no source checkpoint/deploy for this internal primitive, no property lifecycle change. This does not repair legacy FSM endpoint replay behavior. Final API exposure must independently require explicit completion-manage and source grants, both module activations, and a module-level feature independent of variation.

## Controlled FSM completion route and ERP UI, local acceptance

The local router now exposes only source-specific POST /helpdesk/work/field_service/{source_id}/complete. It independently requires helpdesk:work:complete, helpdesk:work:view and operations, both Help Desk/FSM activation, and explicitly enabled module-level work_completion Boolean, default false. The feature exists in every variation and its persisted state survives maintenance/property/consulting/salon/standard activity changes. It does not require or enable the service catalog. No standard role is automatically granted the permission.

Actual JWT API acceptance passes anonymous401, each missing grant403, default/disabled feature409, strict schema422, valid completion200, exact replay200, changed command/stale state409, unknown and other-tenant source404, each inactive module403, one technician increment and one audit. Temporary source rows/users/schema/settings/activation roll back.

Actual full ERP UI passes review/notes/explicit confirmation, native completed after reload, no repeat action, unchanged property native status, catalog-only regression and mobile390 no overflow. Work-read-only roles see no write action. Writable view describes native completion effects rather than incorrectly saying read-only. All colors inherit configured ERP tokens.

Remaining: local only, not source-checkpointed/deployed. General/activity/custom menu precedence remains unchanged. No legacy route replacement, property write path, customer intake, billing, notifications, or complete Help Desk migration. The primitive's deterministic audit ID is a scoped deduplication contract, not a claim that unrelated AuditLog records become globally immutable.

## Hosted acceptance,24November09:46

Source b6a8c76120517af8f4feb203a18c7795cd1bb302 is deployed to the separate test project. Normal ERP Settings, restricted-role list/completion, explicit confirmation, completed reload, unchanged property state, mobile390, disabled409, unchanged general settings/Studio page and no page errors pass. DB postcheck verifies one technician increment/available status and one audit without notes. Exact fixture activation/sector/raw settings restored and bounded source rows/user/audit removed. No new migration or automatic grant. See current-status page for remaining scope.
