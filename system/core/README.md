# Mizan Shared

Code used by every product. Changing anything here affects the system, website, owner
and admin apps, and rebuilds all of them.

## `backend/`: the domain kernel (`mizan-shared`, Python package `app`)

- `app/factory.py`: `create_app(title, routers, …)` builds every API with the same
  middleware, CORS, CSRF, error handling and `/health`.
- `app/core/`: config, errors, pagination, rate limiting. `app/dependencies.py`: the current
  user and `require_perm`. `app/middleware.py`: CSRF.
- `app/models/registry.py` (imports every model so the schema is complete), `app/db/` (engine,
  ordered migrations in `db/migrations.py`, baseline schema, bootstrap).
- `app/framework/`: the module runtime (loader, variants and hooks, screens, scaffold) and the
  package format shared with the SDK (`manifest.py`, `package.py`).
- `app/platform/`: the engines every workspace has (auth, permissions, tenancy, printing,
  licensing, billing, notifications, …), the platform's modules (module centre, scheduler, i18n,
  community modules, themes) and the developer portal's accounts (`developers`).
- `app/activities/<activity>/`: one folder per business activity (ADR-010): its definition
  (`activity.json`, positions, seed), its modules (`modules/<id>/`: models, routers, manifests,
  print templates), its variants of other activities' modules (`variants/<module>/`) and its
  themes. A module's id comes from its `manifest.json`; folder names must be valid on Windows.
- `app/themes/`: Mizan's theme packs. `app/catalog/`: families and legacy ids.
  `app/integrations/`: connectors (Paymob, Fawry, InstaPay, WhatsApp, POS hardware, webhooks).
- `app/onprem/`: server mode for on-site installs (`setup`, `server`, `licence`, `checkin`,
  `state`). `app/platform/licensing/` signs and verifies licence keys, release offers and
  developer certificates; `app/platform/updates/` lists the published installers.

Services depend on it via `pyproject.toml` (`[tool.uv.sources] mizan-shared = { path = "../../system/core/backend" }`);
Docker images install it from the repo root build context.

## `frontend/`: the kit (`@mizan/shared`, imported as `@/`)

- `components/`: shadcn/ui kit, app primitives, motion, logo.
- `lib/`: API client (`VITE_API_URL` per app), formatting, plans, cross-app URLs (`urls.ts`),
  session handoff (`handoff.ts`) and theme packs (`theme.ts`: applies a workspace's theme).
- `stores/`: auth (applies the workspace's theme) and UI (device choices: dark mode, layout,
  density). `i18n/`, `styles.css` (design tokens, Mizan's default values).
- `features/billing/PricingPage.tsx`: used by the website (marketing layout) and the system
  app (in-app upgrades).
