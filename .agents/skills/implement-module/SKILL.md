---
name: implement-module
description: Procedure for scaffolding and implementing a new business module in Mizan
---

# Implement Module Procedure

When tasked with implementing a new module (e.g. `HLT-02`, a planned module of an activity):

1. **Requirements & Domain Inspection:**
   - Read the requirements (`docs/PRODUCT_REQUIREMENTS.md`, the SRS, the module's `README.md` if it is planned).
   - Read `docs/MODULE_STANDARD.md` and inspect peer modules in `system/core/backend/app/activities/<activity>/modules/`.

2. **Scaffold with the project's tool:**
   - `python manage.py module new <activity> <module_id> "<Arabic name>" --name-en "<English>"` creates the backend
     (`activities/<activity>/modules/<id>/`: manifest.json, models, schemas, service, router, hooks, seed, README…)
     and the screens folder (`system/erp/frontend/src/activities/<activity>/modules/<id>/`: index.ts, api.ts, screens/, components/).
     On a planned module it makes it active.
   - `python manage.py module check` must pass.

3. **Data and rules:**
   - Models are `TenantScoped`; add the migration (with RLS) to `app/db/migrations.py`; the model declares the same keys and defaults.
   - Business logic in `service.py`; routes thin, with `require_perm` and permissions declared in the manifest.
   - Another activity's adaptation goes in that activity's `variants/<module>/`, not here.
   - Demo data in `seed.py` (marked `is_demo`).

4. **Screens:**
   - Declare pages in the manifest's `screens` (menus come from activities' `activity.json`, never hand-typed), widgets in `widgets` and register them in `index.ts`.
   - Follow `docs/UI_UX_GUIDELINES.md` and `docs/DESIGN_SYSTEM.md` (tokens only); every state: loading, empty, error, no-permission, full.

5. **Verification & Testing:**
   - Backend tests in `system/erp/backend/tests/`; `python manage.py test backend`; `test e2e` if routes changed.
   - `npx tsc -b --noEmit` and `npm run build` in `system/erp/frontend`.
   - Open the screen in a browser (Playwright), check it, and update docs (`TASKS.md`, the module's README).
