# Salon & Consulting absorption into Help Desk — mapping and write-reconciliation proposal

Status: proposal for review. Implements nothing. Grounded in the 2026-11-24 user
instruction (unify similar capabilities into Help Desk as variations; features
exist in every variation), `docs/helpdesk-unification-impact-map.md` rows
21/22/33/40/49, and the actual models. Nothing here renames source records,
relabels prices, or widens grants.

## 1. What the source domains actually contain (verified against code)

### Salon (`app/activities/salon/modules/salon/models.py`)

| Entity | Shape | Help Desk concept it matches |
| --- | --- | --- |
| `SalonService` (SAL-01) | Catalog entry: name, category, duration, buffer, base_price, consumable_cost, is_active | **Service catalog offering**, not work. Reusable offering identity per impact-map row 21. |
| `SalonAppointment` (SAL-02/08) | Discrete scheduled work: appointment_ref, client, stylist, service_name, station, date/slot, price, native status (`scheduled, in_service, completed, cancelled`), payment_status | **Work view row** (read-side adapter candidate). Native status and payment_status stay salon's. |

### Consulting (`app/activities/consulting/modules/services/models.py`)

| Entity | Shape | Help Desk concept it matches |
| --- | --- | --- |
| `ConsultingEngagement` (CON-01/04) | Long-running commercial container: client, project, billing_model (retainer/hourly/fixed_milestone), contract_value, retainer_balance, hourly_rate, status (`active, review, completed`), dates, partner | **None today.** It is a contract, not a discrete request. Renaming it a ticket is exactly what impact-map row 22 prohibits. |
| `ConsultingTimesheet` (CON-02/03) | Billed time entries under an engagement, with approval semantics | **None.** Time approval and billing stay explicit per row 22. |
| `StatutoryDeadline` | Filing obligations | **None.** Statutory semantics stay explicit per row 22. |

## 2. Read-side absorption mapping (technical, settleable)

Following the f9348e5 registry pattern (`helpdesk/sources.py`):

1. **Add `salon` work adapter** (module id `salon`, per its manifest):
   `salon.models:SalonAppointment`, keys
   `(id, tenant_id, appointment_ref, service_name, status)` — the projection
   description is the native `service_name`, one native field like the two
   existing adapters; `client_name`, stylist, station and slot stay in the
   row's native detail, unchanged. Salon wording and fields are preserved (row 21).
   Gated by `salon` module activation + the caller's existing salon read grant,
   same as the two current adapters. Rows join `/helpdesk/work` as
   read-only native-status items.
2. **Add `salon` catalog projection (separate, later)**: `SalonService` rows
   appear as catalog offerings where the service-catalog feature is on.
   `base_price` is never relabeled a "starting price" automatically (row 33);
   `consumable_cost` never enters any customer-facing discovery (row 33).
   This needs the catalog contract's offering-shape mapping and is a distinct
   slice from the work view.
3. **Consulting contributes no adapter now.** No discrete request-shaped entity
   exists in the consulting module; engagements/timesheets/deadlines are
   contract, billing, and filing concepts. The map's "where lifecycle matches"
   clause matches nothing today, and inventing a ticket shape for a retainer
   engagement would violate row 22. If the user later wants engagements visible
   in Help Desk, that is a new explicit projection decision, not an adapter.

## 3. Write-reconciliation contract (prerequisite for ANY creation path)

Required before Help Desk intake can create salon appointments or any future
source record (the gate the impact map sets for the write path, same one that
gates FSM creation):

1. **Single writer**: Help Desk intake calls the source module's own creation
   service. The native row in the source table is the only record; Help Desk
   never stores a parallel ticket. Read adapters project; they never hold state.
2. **Idempotency**: intake carries a client-supplied idempotency key; the source
   service stores `(tenant_id, key)` and returns the existing native row on
   replay. No double booking/order on retry or double-submit.
3. **Authorization**: the caller must hold the source module's own create grant
   at call time; Help Desk's intake permission is additive, never a substitute
   (row 40). Tenant matching is enforced in the source service, not assumed.
4. **No status/price conversion**: native status enums, prices, and billing
   fields are written exactly as the source module defines them (rows 22/33).
5. **Audit**: the intake record references the created native row
   `(source, source_id)` for traceability; cancellation/undo means the source
   module's own cancel path, never a Help Desk-side delete.
6. **Failure mode**: if the source create fails, intake reports the source's own
   error; nothing is half-created in Help Desk.

## 4. Settled technically vs user-only business decisions

**Settled by the impact map + originals + domain evidence (no user question needed):**

- No renaming of salon/consulting records into tickets (map row 22; originals
  ask for unification as variations, not relabeling).
- No automatic price/tax conversion or relabeling of `base_price`,
  `hourly_rate`, `contract_value` (map row 33).
- Consulting has no work-adapter today because it has no request-shaped entity
  (code-verified above).
- Write path stays gated on the reconciliation contract in section 3.

**Genuine business decisions only the user can make (NOT blocking current work):**

1. Whether salon appointments appearing in the Help Desk work view is the
   desired unification depth for the salon variation, or whether salon should
   stay catalog-only in Help Desk (appointments visible only in the salon
   module's own calendar). The originals say "unify similar things"; whether
   appointment scheduling is "similar" to maintenance tickets is a product
   judgment, not a technical one.
2. Whether `SalonService` entries should be authorable from the Help Desk
   catalog (write) or only projected (read) — authoring from two surfaces has
   UX and ownership implications beyond the technical contract in section 3.

## 5. Proposed next slices (ordered, each independently shippable)

1. Salon work-view read adapter + tests + live-PG check extension (this is the
   only immediately implementable absorption; ~same size as f9348e5).
2. Write-reconciliation contract doc review with user before any creation path.
3. Salon catalog projection (needs the catalog offering contract; separate).
4. Consulting: nothing until a discrete request-shaped entity exists or the
   user explicitly asks for engagement visibility.
