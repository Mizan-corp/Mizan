# Architecture Rules for Antigravity

- **Module Isolation:** Modules in `backend/app/modules/<activity>/<name>/` must not directly import internal private implementations of peer modules. They must interact via shared core services or documented public interfaces.
- **Tenancy Boundary:** Every database query that writes or reads tenant business data must participate in the active tenant session. Never bypass tenant scoping.
- **No Circular Imports:** Always keep backend routes, schemas, and models cleanly layered.
- **Shared Code Audit:** Before altering files in `backend/app/core/`, `backend/app/models/`, or `frontend/src/components/`, perform a full dependency search across all modules.
