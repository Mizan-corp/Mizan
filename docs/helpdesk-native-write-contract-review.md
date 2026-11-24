# Native work writes: consolidation review

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
