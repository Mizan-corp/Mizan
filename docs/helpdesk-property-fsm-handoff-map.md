# Property request to field-service handoff: source map

24 November 2026. Read-only design and acceptance fixtures. Writable dispatch, link schema and automatic source-status changes are NOT implemented. User decision on manual reviewed versus automatic dispatch is pending.

## Grounded source boundary

RE-08 in docs/srs/06_INDUSTRY_SPECIFICATIONS_PHASE5_PROJECTS.md calls for property complaints to dispatch facility-engineer work orders through FSM-02. The source ticket model has no assignee/FSM link. The source router only lists/creates tickets, with no ticket status-update endpoint. Its UI creates/lists tickets and exposes cost/CAM separately. FSM creation starts dispatched and requires more fields than the property ticket provides. Existing route contracts must remain intact until compatibility is proved.

## Field map, no inferred personal details

| Property source | Proposed handoff use | Gap/guard |
|---|---|---|
| ticket id/reference | Immutable origin identity and review heading | Never replace either native identity; require stable retained link |
| unit_id | Resolve same-tenant unit/property for authorized review | Both source entities must still exist and match tenant at commit |
| category | Review context | Not a technician skill match or automatic equipment mapping |
| description | Candidate work issue, explicitly reviewed | Private source-authorized free text, not a public catalog description |
| reported_by | Original report attribution only | Not proof of client identity, contact number or notification permission |
| cost_egp/CAM | Stay in property/accounting | Never copy into catalog starting price, invoice or dispatch payment |
| native status | Expected-state guard and source context | No automatic resolved/assigned rewrite without its own approved rule |
| property location | Candidate site context if complete | Property city/district is not necessarily a complete visit address |
| none | Client name/phone, equipment, SLA, technician, van, visit date | Authorized dispatcher must supply/confirm; do not invent |

## Proposed safety contract for a manual reviewed slice

Not an execution authorization. Requires exact user product decision and a final native contract before implementation.

- Both modules active, explicit handoff permission plus common read and source operations grants. Do not add default grants.
- Explicit origin ticket/tenant, expected native state, stable operation identity and a retained source-to-work link. No unchecked duplicate-work button.
- Review shows exactly which additional fields will be recorded, selected same-tenant technician and any missing prerequisites. No nearest-qualified claim without skills/location data.
- One transaction for link, work row and narrow controlled event. Row locks and unique origin/operation constraints, with clear retry/conflict behavior. Link identity must not depend only on mutable technician name.
- Leave property cost, CAM, request status and occupancy unchanged in the first slice. Preserve legacy routes. FSM completion does not automatically resolve the property request.
- No notification, customer portal, external contractor, parts, invoice or paid booking effect.

## Acceptance fixture matrix to implement after decision

1. Valid same-tenant ticket/unit/property and explicit dispatcher selections, one linked work row, both original IDs/references retained.
2. Same operation exact retry produces no duplicate link/work/audit; changed command409. Two independent concurrent transactions exercise both paths.
3. Missing permission403, either module inactive403, feature disabled409 if a feature is introduced. Every variation retains the same feature existence/state.
4. Foreign tenant ticket/unit/technician404, unknown/missing source404; invalid/unmapped native state rejected explicitly, never silently normalized.
5. Technician or origin changes between review/commit conflict, no partial work/link/audit. Simulated audit failure rolls back all effects.
6. Cost/CAM, original native status, original reporter and unrelated source counts unchanged. No client phone derived from reporter.
7. Actual ERP review/confirm/reload and source link readback on desktop/mobile, configured theme. No action for read-only roles; retry after uncertain failure cannot dispatch twice.
8. Regression: catalog edit/archive, intake/history, controlled completion and original Studio remain unchanged. Cleanup restores exact raw feature state/activation/fixture identities. No destructive source migration.

## Remaining choices, not silent defaults

Manual reviewed versus automatic dispatch is pending. If manual is approved, agree whether only one active linked work order is allowed per property request before implementing repeat dispatch/reopen. Completion synchronization, reassignment and portal submission remain later contracts. The first slice must not claim a complete property lifecycle.
