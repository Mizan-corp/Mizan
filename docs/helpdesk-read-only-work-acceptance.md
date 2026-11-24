# Help Desk read-only work adapters

Historical local acceptance record. Current implementation: see [Help Desk current status](helpdesk-current-status.md). Hosted test now also has a separately gated source-specific FSM completion capability; read-only roles remain read-only.

Status: local acceptance only, not committed or deployed. Hosted service catalog remains on e7399f387d3d2d107f142257654bba371d83f0b4. Full Help Desk unification is incomplete.

## Accepted

- Shared GET /helpdesk/work preserves native FSM/property table, ID, reference and status. No writes or data movement.
- Both helpdesk:work:view and operations grants required; each source module must be active, with the common Help Desk activation guard retained.
- Narrow output excludes dedicated customer phone/address, reporter, technician, cost and private completion-note fields. Native description is preserved and requires source permissions; it is not public-safe content.
- A blank/malformed native row remains untouched and produces explicit invalid_source_rows coverage diagnostics. Healthy rows still render and desktop/mobile warning pixels are accepted.
- Actual JWT tests pass for both missing-grant combinations, source module gating and a real other-tenant source row exclusion.
- Actual ERP shell desktop and 390px mobile UI passes for work-only role, reload, no catalog form, no overflow, no page errors. Screenshots inspected with configured ERP theme.
- Temporary users, source rows, source schema and module activation are rolled back and checked after each harness.

- Common-work-only without operations gets page permission denial; no-grant role gets route Guard denial. Neither renders work rows.

## Not accepted yet

- Not a shared writable lifecycle. Original sector screens/transitions and histories are unchanged.
- Latest-per-source 100 cap and truncated_sources pass with 101 actual FSM rows, while the separate property row remains visible.
- Catalog-only role create/reload/archive/reload/restore passes after shared header revision. Work section stays hidden for catalog-only role.
- Work-only users can open the route directly, but activity/custom role menus may omit it. General default includes the screen; existing activity/role/workspace precedence is deliberately retained. Decide a non-destructive discovery route rather than overwriting menus.
- Local snapshot preserved. No Git commit or new deployment for this delta.

## Evidence

Local API harness: /tmp/mizan-helpdesk-work-check.py.
Full-shell visual harness: /tmp/mizan-helpdesk-work-visual.py and /tmp/mizan-helpdesk-work-ui.py.
Desktop/mobile screenshot names: mizan-helpdesk-work-local-desktop.png and mizan-helpdesk-work-local-mobile.png.
