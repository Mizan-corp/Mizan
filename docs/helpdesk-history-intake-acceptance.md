# Shared work history and property request intake

Status: locally accepted, not deployed. Hosted test still runs b6a8c76120517af8f4feb203a18c7795cd1bb302 (common read and controlled FSM completion). This is not full Help Desk unification.

## History

Read-only per-source/source-ID route requires common work-read, operations, common activation and active source. Looks up the exact tenant-owned row first. Exposes only recognized controlled create/completion events, native before/after status and recorded time, no actor, reporter, completion notes, fingerprint or unrelated audit entities. Latest100 cap and unreadable-event diagnostic prevent false completeness. UI shows readable local time and timezone, and explicitly says older legacy history is unavailable, not that nothing happened. Property source creation gets its controlled event; pre-existing property tickets may have none. No fabricated backfill.

## Internal property intake

Independent work_intake Boolean default false exists in every variation. Needs helpdesk:work:create, helpdesk:work:view, operations, common module and real_estate activation. Minimal unit choices join same-tenant property and unit only. Creates native property ticket with generated stable ID/reference, selected unit identity, caller category/description/reporter and native open state. Cost is zero and CAM false; no API money/status fields allowed. No FSM dispatch, customer messaging, invoice or payment.

Scoped operation-ID advisory lock and audit identity make exact same-user retry replay-safe. Changed command409. Actual independent PostgreSQL transactions prove duplicate waits then replays, changed command conflicts, exactly one ticket and audit. Disposable uniquely named test schema removed and checked. Unit row lock and same-tenant parent check prevent cross-tenant linking. Unknown/other-tenant unit404. Input is strict and bounded.

## Local acceptance

Actual JWT routes test anonymous401, missing grants403, default/disabled feature409, strict422, unknown/other-tenant unit404, replay once and changed409, both inactive modules403, feature state retained across all4activity variants plus standard. Unit choices exclude other-tenant records. New property row retains selected unit/open/zero-cost/no-CAM and does not create FSM work. History shows exactly controlled create event without private input. Malformed controlled history shows diagnostic, unrelated events excluded.

Actual ERP UI tests unit choice/create/reload/open/history, mobile390 no overflow and configured ERP theme. History/completion and catalog role regressions passed before intake addition; final combined regression is still required. Fixtures are outer-transaction rolled back; independent concurrency disposable schema cleanup verified. Screenshots inspected after event loading settled.

## Remaining

No shared property assignment/resolution lifecycle, dispatch link, full legacy history, generic/customer intake, visitor projection or billing. Existing routes and source data contracts remain unchanged. Intake UI retries same operation after uncertain failure, but drafts are not retained across full browser reload. Existing offering edit remains outstanding. No source pin/deploy yet for this slice.
