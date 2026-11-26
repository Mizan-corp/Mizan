# Architecture Rules for Antigravity

- **Activities are folders:** a business activity is `system/core/backend/app/activities/<activity>/` (activity.json, positions.json, seed.py, `modules/<module>/`, `variants/<module>/`, `themes/`), screens in `system/frontend/src/activities/<activity>/{modules,variants}/` (ADR-010). An activity's adaptation of another activity's module lives in the adapting activity; a module's own defaults stay in `<module>/variants/standard/`.
- **Module Isolation:** Modules must not import peer modules' internals; they interact through a module's `service.py`, shared platform services, or extension points (`emit("<module>.<moment>")` and variants' `hooks.py`). Never `if sector == ...`.
- **Tenancy Boundary:** Every query on workspace data runs with the workspace bound (`TenantScoped`, RLS, the `mizan_app` role). Platform rows (no `tenant_id`) are written only with no workspace bound (#112).
- **Permissions decide:** routes check `require_perm("<id>")` with ids declared in a manifest; no role-name checks.
- **No Circular Imports:** keep routes, schemas, services and models layered.
- **Shared Code Audit:** before changing `system/core/backend/app/{core,framework,platform}/` or `shared/frontend/src/`, search every product that uses it (system, website, owner, admin, installer, SDK).
- **One validator:** `app/framework/manifest.py` is shared with the SDK (`sdk/python/mizan_sdk/manifest.py`, a byte copy kept by a test); change both together.
