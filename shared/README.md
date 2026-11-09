# Mizan Shared

Code used by all three products. Changing anything here affects the system, website
and admin apps, and rebuilds all of them.

## `backend/`: the domain kernel (`mizan-shared`, Python package `app`)

- `app/factory.py`: `create_app(title, routers, …)` builds every API with the same
  middleware, CORS, CSRF, error handling and `/health`.
- `app/core/`: config, tenancy (ORM filter + `before_flush` stamping + RLS GUC), security,
  RBAC/ABAC, plans and sectors.
- `app/models/`, `app/schemas/`, `app/services/`, `app/db/` (engine, tracked migrations,
  SQL in `db/sql/`).
- `app/api/routers/`: the ERP endpoint library (mounted by the system API).
- `app/modules/`: the 48 domain modules: models, routers, manifests, print templates.

Services depend on it via `pyproject.toml` (`[tool.uv.sources] mizan-shared = { path = "../../shared/backend" }`);
Docker images install it from the repo root build context.

## `frontend/`: the kit (`@mizan/shared`, imported as `@/`)

- `components/`: shadcn/ui kit, app primitives, motion, logo.
- `lib/`: API client (`VITE_API_URL` per app), formatting, plans, cross-app URLs (`urls.ts`)
  and session handoff (`handoff.ts`).
- `stores/`: auth and UI stores. `i18n/`, `styles.css` (design tokens).
- `features/billing/PricingPage.tsx`: used by the website (marketing layout) and the system
  app (in-app upgrades).
