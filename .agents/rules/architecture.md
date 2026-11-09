# Architecture Rules for Antigravity

- **Module Isolation:** Modules in `shared/backend/app/modules/<activity>/<name>/` (screens in `system/frontend/src/modules/<activity>/<name>/`) must not directly import internal private implementations of peer modules. They must interact via shared core services or documented public interfaces.
- **Tenancy Boundary:** Every database query that writes or reads tenant business data must participate in the active tenant session. Never bypass tenant scoping.
- **No Circular Imports:** Always keep backend routes, schemas, and models cleanly layered.
- **Shared Code Audit:** Before altering files in `shared/backend/app/core/`, `shared/backend/app/models/`, or `shared/frontend/src/components/` (used by the system, website and admin apps), perform a full dependency search across all modules.
