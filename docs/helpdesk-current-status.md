# Help Desk current implementation status

As of 24 November 2026. This page is the current status; earlier dated implementation notes are historical checkpoints, not current limitations or proof of later work.

## Usable on the isolated hosted test

Test URL: https://mizan-studio-feature-test.vercel.app/

Source: ba722ca8a5bb39e70bd91dc2baca09cdadb51ad8 on feat/studio-render-parity. No production replacement or merge.

- General-owned Help Desk module, standard plus maintenance/property/consulting/salon variations.
- Independent service_catalog, work_completion, work_intake and work_actuals Boolean settings. All four exist in every variation, default off, and changing workspace activity preserves saved state.
- Private service offering list/create/edit/archive/restore, explicit two-decimal starting amount/currency. No invoice, booking or payment. Catalog view/manage permissions are separate.
- Shared read view of active FSM work orders and property maintenance tickets. Native table/ID/reference/status preserved. Requires common work-read plus operations and source activation. Does not move records or rewrite native status.
- At most the latest 100 rows per source, with explicit truncation and malformed-source-row coverage diagnostics.
- Source-specific FSM completion with notes/review/confirmation, expected native status, replay-safe operation ID, row/technician locking, one technician completion effect and one audit. Requires explicit completion plus work-read plus operations permissions, Help Desk and FSM activation, and enabled work_completion. Unknown/ambiguous technician fails closed. This capability is available in every variation; the active FSM source is a dependency, not a variation gate.
- Native same-tenant property/unit request intake, zero cost/no CAM, no automatic dispatch. Separate create/read/operations grants, source activation and independent work_intake toggle. Scoped operation replay and unit/operation locks prevent duplicate creation.
- Source-bound controlled history with current native status, local time and timezone, event coverage diagnostics and explicit legacy-history limitation. No fabricated older chronology.
- Configured ERP theme on Settings and Help Desk, desktop and mobile.

Dedicated contact/cost/completion-note fields are excluded from the common list. Native free-text descriptions still require source access and are not safe for visitor/public projection.

## Acceptance completed

Actual JWT/effective-role tests cover anonymous, missing grants, strict input, source and module activation, disabled features, same-tenant and other-tenant access, exact replay and stale/changed commands. Actual independent PostgreSQL transactions prove duplicate completion waits then replays while a different command conflicts, with one counter increment and one audit. Simulated failure rolls source/effect/audit back together.

Hosted normal ERP acceptance covers feature save/reload, both source rows, review/notes/confirmation, native completed after reload, unchanged property state, mobile390 no overflow, disabled completion409, unchanged general settings and original Studio page, and no page errors. Hosted DB postcheck verifies one technician increment and one audit without notes.

Only bounded test rows and a temporary restricted role were used. Exact original module activation, sector and raw feature settings were restored; fixture source rows/user/completion audit were removed and checked. Source tables already existed with forced RLS; this deployment applied no schema migration. Existing workspaces/users are not silently activated or granted new permissions. Access depends on the workspace's explicit configuration and grants. Screenshots record temporary acceptance data, not retained demo records.

Hosted intake/history acceptance additionally verified restricted-role create/reload, unit retention, native open status, exactly one create audit without private description/reporter, no FSM dispatch or technician increment, disabled409, and mobile390 no overflow. Exact settings, activation and all bounded fixtures restored. No migration.

## Incomplete

- Full Help Desk unification and original user-facing builder success criterion are not complete.
- Native FSM creation remains on its source screen. No common generic/customer request intake or property status update contract is implemented. Native property/unit intake is hosted.
- Existing source routes/tables/IDs/histories are retained. The legacy FSM completion endpoint remains unchanged; its pre-existing repeated-completion counter behavior is not fixed by the new controlled route.
- No automatic property-to-FSM conversion, dual-write, legacy history migration or deduplication.
- Consulting retainers/time/billing, salon schedules/treatment records and hotel room availability are not silently converted into tickets.
- No customer portal, public service discovery projection, quote acceptance, scheduling, notification, billing or payment.
- Existing activity/role/workspace menu precedence is preserved. A customized layout may need an explicit screen placement; no customized menu is overwritten.
- Existing-offering edit is hosted with expected-values stale-edit protection, exact desired-state retry and stable identity/archive state. This is not final-price approval, billing or request editing.

## Latest offering edit acceptance

Hosted deployment dpl_3ry5MJgAMdHoa2j9V229142aKD6f passed restricted-role all-four-field edit/save/reload, stable ID, stale concurrent409 and close/reload recovery, archived edit retaining archive state, themed desktop/mobile390 and no page errors. DB confirmed three expected update audits and excluded descriptions. General settings unchanged; original static Studio entry byte-identical. Exact raw feature settings, module activation and original offering-ID set restored; bounded offering/audits/user removed. No schema or sector change. Catalog restored off.

## Shared execution actuals acceptance, 11:34

Deployment dpl_9qMcrQ2zbi6ESKbZXZKmJUm9Zz2Z is now canonical. The fourth work_actuals feature records dated task/labor/material actuals on the same native source, retains correction chains and resource-name snapshots, and independently gates cost/selling entry and visibility. Positive Decimal quantities, explicit unit/currency/provenance, separate currency subtotals and unknown-rate diagnostics are enforced. Returns are separate recorded buckets, never automatic credits.

Actual JWT hosted API acceptance passes default-off, save/replay/conflict, retained correction and restricted monetary projection. Hosted ERP UI acceptance passes labor1.5h, installed2pieces/allowed warehouse, save/full reload, correction to2h retaining the original, known40EGP cost and90EGP proposed selling with1unknown material line, read-only no form, desktop/mobile390 with no overflow/page errors. Screenshot is a normal settled viewport. Protected candidate assets/API were exercised through authenticated request transport, not a local replacement API.

Only additive atomic migration v111 was applied to the isolated test DB. ForcedRLS and a table-local append guard protect history even if the existing shared grant helper widens grants. App role cannot UPDATE/DELETE/TRUNCATE history. No existing grants, native source rows or module state were changed by the migration. Exact original settings/activation/sector were restored after acceptance; bounded execution/source/resource/users removed, empty history verified, temporary credentials deleted. Fourth feature is restored OFF.

This is non-posting shared foundation only. Stock, payroll, accounting, invoice, payment and final customer charge are not created. Operational completion remains separate from costing completeness. User's latest direction is to return to common core SDK/web builder work now, then review business activities one by one. Specialty gaps above are deferred, not blockers to common builder progress.
