# Help Desk catalog, internal verified slice

24November2026. Local integrated source, not deployed. Full Help Desk unification is incomplete.

## Delivered in local acceptance

- General-owned Help Desk registered in normal backend registry, with a normal ERP route and module definition.
- Optional service_catalog typed Boolean setting. Available in every variation and stored independently. Actual Settings roundtrips across maintenance, property, consulting, salon and standard retained the enabled value.
- Internal offering list/create/archive/restore with starting amount, explicit supported currency, fixed precision and active/archive flag. No product stock, order, booking, final quote or payment meaning.
- Effective-role read/manage permission gates, module activation gate and feature gate. Custom read-only, no-grant and writer roles tested through actual JWT sessions.
- Tenant-scoped model, explicit tenant query predicates, enforced RLS and atomic additive Python migration path. A real other-tenant row stayed hidden through ORM/raw RLS and returned404 on archive.
- Normal full ERP UI create/save/fullreload/archive/fullreload/restore, desktop/mobile390, actual pixels inspected. No page errors. TypeScript and full ERP build passed.

## Migration contract

v110_helpdesk_offerings uses the existing Python migration branch, which propagates errors rather than the SQL branch's catch-and-continue behavior. The new migrate() applies its DDL/grant/RLS checks inside a savepoint. Missing application role or incomplete RLS/grants fails closed. An existing untracked helpdesk_offerings table fails for inspection rather than being silently accepted. Only a successful return allows the existing runner to record the migration. No shared runner behavior changed.

The migration has only been exercised inside an outer rollback. Nothing has been applied persistently or hosted. Source registration does not mean the hosted database has the table.

## Activity integration

Maintenance, property, consulting and salon activity configurations add the shared catalog and select their Help Desk variation. Existing modules, original menus, legacy tables and routes remain unchanged. General's default menu includes Help Desk for an explicitly activated module; it is not added as a mandatory default module to every workspace. Existing per-role/workspace custom menus retain precedence and may need an explicit layout edit to show the new screen. Do not silently overwrite these customizations.

This is additive catalog integration, not completed consolidation of sector work. The request/work owner still needs working adapters, source role mapping, native lifecycle transitions, history and compatibility acceptance before moving those screens.

## Money and currency

Starting prices are not payable totals. Supported initial subset: EGP, USD, EUR, GBP, SAR, AED, QAR, at two decimal places. Three-decimal currencies are rejected until precision support is designed. No default currency is inferred. Nothing converts existing salon base price, consulting rate or inventory retail price into a new offering.

## Known integration issue contained

Existing central audit service writes older action/changes/note columns, while the declared model and actual schema use action_type/details/reason. New Help Desk writes use AuditLog directly and fail with the transaction if audit insert fails. Two expected audit events were verified. Shared audit service and schema remain unchanged; broader repair is separate.

## Verification evidence

Isolated acceptance harnesses are private test helpers, not shipped application code. All temporary tables, users, roles, second tenant, module settings and activation were rolled back and checked absent or exact-original. An interrupted full-ERP harness was followed by direct state verification before retry; the bounded-shutdown rerun passed cleanly. Screenshot files show local execution only, not hosted availability.

## Remaining work

Repository checkpoint/readback; hosted isolated candidate with approved additive migration and rollback strategy; hosted normal UI/Settings acceptance. Legacy request/work adapters and full activity consolidation. Public builder projection/runtime, visitor intake, customer identity, rate limits, notifications, appointments and payments remain separate unimplemented boundaries. No production changes or destructive migrations.
