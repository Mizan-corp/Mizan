# Mizan ERP — System Architecture

## 1. Architectural Style
Mizan is built as a **Modular Monolith** optimized for developer velocity, transaction integrity, and deployment simplicity:
- **Shared Enterprise Kernel:** Multi-tenancy resolution, database session lifecycle, audit logging, security context, and notification dispatch.
- **Pluggable Domain Modules:** Each in its activity's folder, `shared/backend/app/activities/<home_activity>/modules/<module_id>/` (manifest, models, router, templates), with screens in `system/frontend/src/activities/<home_activity>/modules/<module_id>/`; an activity also holds its variants of other modules and its themes (ADR-010); platform modules in `app/platform/`, connectors in `app/integrations/`, the loader in `app/framework/` (ADR-006).

```
                    ┌─────────────────────────────────┐
                    │       Web & Mobile Clients      │
                    │   (React 19 + Vite + Tailwind)  │
                    └────────────────┬────────────────┘
                                     │ HTTPS / WSS
                                     ▼
                    ┌─────────────────────────────────┐
                    │   FastAPI Gateway / Middleware  │
                    │   - Tenant Context Resolver     │
                    │   - Auth & Session Cookie / JWT │
                    │   - RBAC & ABAC Enforcer        │
                    │   - Audit Trail Interceptor     │
                    └────────────────┬────────────────┘
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
┌──────────────────────────────┐                       ┌──────────────────────────────┐
│       Healthcare Core        │                       │     Commercial & Retail      │
│ - HLT-01 Organization Mgmt   │                       │ - POS & Cashier Shifts       │
│ - HLT-02 Patient Identity    │                       │ - Inventory & Warehouses     │
│ - HLT-03 Appointments        │                       │ - Sales & Invoicing          │
│ - HLT-05 EMR & Clinical Enc. │                       │ - Purchase Orders            │
└──────────────┬───────────────┘                       └──────────────┬───────────────┘
               │                                                      │
               └───────────────────────────┬──────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────┐
                    │    SQLAlchemy 2.0 Async ORM     │
                    │  - TenantScoped Base Model      │
                    │  - Automatic Audit Flush Hook   │
                    └────────────────┬────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │  PostgreSQL (own server, RLS)   │
                    │   - Tenant Isolation Policies   │
                    │   - Immutable Audit Log Table   │
                    └─────────────────────────────────┘
```

## 2. Directory Layout

Mizan ships as **four products that are developed and deployed separately**, on top
of one shared kernel and one PostgreSQL database; in production the four APIs run in one process
and nginx serves the four apps (ADR-011, `deploy/server/`; see `docs/decisions/ADR-003-separate-apps.md` and `ADR-004-owner-accounts-and-payments.md`). The system API and app also run on the client's own computers (`installer/`, ADR-005).

| Folder | What it is | Frontend (served at) | Backend (served at) |
|---|---|---|---|
| `system/` | The ERP tenants use every day | `system/frontend` → `<workspace>.allmizan.live` | `system/backend` → `api.allmizan.live` |
| `website/` | Landing, pricing, docs, signup, onboarding, the developer platform | `website/frontend` → `allmizan.live`, `dev.allmizan.live` | `website/backend` → `web-api.allmizan.live` |
| `owner/` | The owner panel: an owner's workspaces, subscriptions, Paymob payments (Arabic) | `owner/frontend` → `allmizan.live/owner` | `owner/backend` → `owner-api.allmizan.live` |
| `admin/` | The admin panel (English, Mizan team only) | `admin/frontend` → `allmizan.live/admin` | `admin/backend` → `admin-api.allmizan.live` |
| `shared/` | Code every product uses | `shared/frontend` (design kit) | `shared/backend` (domain kernel) |
| `installer/` | Single-device and LAN installs (ADR-005) | `installer/setup` (Mizan Setup, Tauri) | `installer/server` (mizan-server, PyInstaller) |
| `sdk/` | `mizan-sdk` and the `mizan` CLI for outside developers (ADR-007, ADR-010) | — | `sdk/python` |

The website app also serves the **developer platform** at `dev.allmizan.live` (under `/dev`
elsewhere): its home, the developer portal and the developer docs, backed by the website API
(ADR-007 D6).

- `shared/backend/` — installable Python package `app` (`mizan-shared`):
  - `app/factory.py`: builds every service (middleware, CORS, CSRF, errors, health).
  - `core/`: the kernel: config, exceptions, pagination, rate limiting.
  - `models/registry.py` (imports every module's models so the schema is complete), `db/` (engine + tracked SQL migrations in `db/sql/`). Models and schemas live in their module or platform engine.
  - `framework/`: the module runtime (the loader, variants and hooks, the module template and
    scaffold) and the package format shared with the CLI (`manifest.py`: community modules,
    entities, themes and activity packages; `package.py`: `.mzm` build, sign, verify).
  - `platform/`: the engines every workspace has (auth, permissions, notifications, printing,
    settings, billing, …), the platform's modules (module centre, scheduler, i18n, `community`
    modules, `themes`) and the developer portal's accounts (`developers`).
  - `activities/<activity>/`: one folder per business activity (ADR-010): `activity.json`,
    `positions.json`, `seed.py`, `modules/<module>/` (every module, including the core ERP in
    `activities/general/modules/*`: sales, pos, inventory, purchases, finance, hr, contacts,
    operations, reporting), built or planned, in the standard structure (docs/MODULE_STANDARD.md),
    `variants/<module>/` (how the activity adapts another activity's module) and `themes/`.
  - `themes/<id>/theme.json`: Mizan's theme packs; `catalog/`: families and legacy ids;
    `integrations/`: connectors.
- `system/backend/`: `main.py` + `system_api/` (route list, tenant resolution, tenant-side platform endpoints).
- `website/backend/`: `main.py` + `website_api/` (plans, self-serve signup, the developer portal's `/developers` API).
- `owner/backend/`: `main.py` + `owner_api/` (account, workspaces, billing and the Paymob callback).
- `admin/backend/`: `main.py` + `admin_api/` (one router per page: overview, workspaces, billing, activity, team, system).
- `shared/backend/app/onprem/`: server mode for on-site installs (one address for app + API, licence gate, cloud check-in, first-install setup).
- `installer/`: `server/mizan_server/` (install engine, service runner, CLI), `setup/` (the wizard, desktop app, headless installs), `build.py`, `stamp.py`, `ci_smoke.py`.
- `shared/frontend/src/`: kit components, API client, auth/UI stores, i18n, styles, plans, pricing page, cross-app URLs and session handoff.
- `system/frontend/src/`: app shell, ERP features, tenant routing, `activities/<activity>/{modules,variants}/` (each activity's screens), `platform/` and `integrations/`.
- `website/frontend/src/`: marketing pages, the user docs, and `features/developers/` (the developer platform: home, portal, developer docs; English by default).
- `sdk/python/`: `mizan-sdk` (`mizan` CLI, `MizanClient` for `/ext/v1`, `verify_webhook`).
- `owner/frontend/src/`: the owner panel pages and the welcome tour.
- `admin/frontend/src/`: the admin panel pages.
- `docs/`: System documentation, architecture decision records, and API specs.
- `.agents/`: Antigravity engineering rules and procedural skills.

Import aliases (frontends): `@/` is the shared kit, `@app/` is the current app, `@activities/` (system only) is the activities' screens.

## 3. Deployment Modes (ADR-005)

A workspace runs in one of these, chosen when it's created:

| Mode | Where the data lives | How it's reached |
|---|---|---|
| Cloud | PostgreSQL on Mizan's server; uploaded files on its disk | `allmizan.live` (website, `/owner`, `/admin`) and `<workspace>.allmizan.live` (ERP), through Cloudflare to Mizan's server (ADR-008, ADR-011) |
| Single device | A private PostgreSQL 16 on the computer | `http://127.0.0.1:47800`, in a Mizan app window |
| LAN | A private PostgreSQL 16 on the shop's server | `https://mizan.local` (mDNS) or the server's address, HTTPS with the install's own CA |
| Bring your own database | The owner's PostgreSQL | Planned (#91) |

```
  Owner panel ──download──▶ Mizan Setup + licence (.mzn)
                                   │ installs
                                   ▼
  ┌──────────── client computer ─────────────────────────────┐
  │ service: mizan-server run                                 │
  │   ├─ PostgreSQL 16 (127.0.0.1, own cluster, daily dumps)  │
  │   └─ uvicorn: system API (/api) + built app, MIZAN_MODE   │
  │        └─ licence gate: expired/revoked → read-only        │
  └───────────────┬───────────────────────────────────────────┘
                  │ check-in when online (optional)
                  ▼
        owner-api /installations/check-in → renewed licence key
```

- **One code base.** The on-site server is the same system API and app, switched by
  `MIZAN_MODE` and the app's `VITE_DEPLOYMENT=onprem` build; it holds exactly one workspace,
  created from the licence (same id, name, sector and modules as in the cloud).
- **Licences** are Ed25519-signed (`MZN1.<payload>.<signature>`, `app.platform.licensing`),
  verified offline against the public key built into the app, and extended by
  `activate_invoice` when the owner pays.
- **Releases** (ADR-011, `deploy/server/`): a push to `master` is a release
  (`.github/workflows/deploy-server.yml`). The API and web images build on GitHub while CI runs
  and go to GHCR; when CI passes, the runner on Mizan's server backs up the database, migrates it
  (`manage.py db migrate --production --no-backup`), and switches the services
  (`deploy/server/deploy.sh`), keeping the previous release for rollback. Migrations must stay
  backward compatible (the old code serves until the switch). Re-run by hand: Actions → Deploy
  (server) → Run workflow. The web image includes the `mizan-sdk` wheel
  (`dev.allmizan.live/sdk/`).
- **Uploaded files** (logo and its PWA icons, sign-in cover, product images, purchase invoice
  images) go through one service, `app/framework/files.py` (#114). It writes to `UPLOAD_DIR`
  (in production `/srv/data/mizan/uploads` on the server), served at `/uploads`; it can also use
  Vercel Blob (`BLOB_READ_WRITE_TOKEN`), and on Vercel without the token uploads are refused. Each file is
  recorded in `workspace_files` (kind, owner, size): a replaced file is deleted, the storage quota
  counts real sizes, and deleting a workspace in the admin panel deletes its files.
- **Platform tables** (`licences`, `installations`) live in the cloud database; nothing
  from the client's business data is sent to the cloud.

## 4. The extension platform (ADR-007, ADR-010)

Outside developers build on Mizan with the same framework Mizan's own activities use.

| Package (`.mzm`, `kind`) | What it is | Where it installs |
|---|---|---|
| `community` | A declarative module: entities (records), screens drawn from them, permissions, menu items, scopes, webhooks | A workspace's module centre → وحدات المطورين; records in `ext_records`, installs in `community_modules` |
| `theme` | A theme pack: design tokens for light and dark, fonts, radius, shadows, motion | The module centre → المظاهر; `workspace_themes`; the workspace's theme is `tenants.palette["name"]` |
| `activity` | A whole business activity in the layout of `activities/<id>/`: its modules, variants (fields, terms, settings), themes, menus, roles, seed data | Validated and signed now; running it in a workspace comes with #107 |

- **Signing**: packages are zips signed with a developer's Ed25519 key; Mizan certifies the key
  (`MZD1` certificate) in the developer portal, so every install verifies packages offline. Cloud
  installs also refuse keys revoked in the portal. Module ids start with the team's handle.
- **Checks**: one validator (`app/framework/manifest.py`) for the platform and the CLI (the SDK
  ships a byte copy, kept identical by a test); activity packages are also checked against
  Mizan's catalogue (modules, screens, widgets, records, themes). Themes allow only known tokens,
  safe colour formats and readable contrast.
- **Servers**: an installed module's server calls `/ext/v1` with its installation token (`mzx_`,
  only the scopes the owner approved, one workspace) and receives signed webhooks
  (`Mizan-Signature`, retried for about a day by the hourly `community_webhooks` job).
- **Developer portal** (`dev.allmizan.live`, website app + `/developers` on the website API):
  developer accounts (separate from owners), teams, members, signing keys, CLI tokens (`mzd_`),
  and the developer docs. It speaks English by default (`Accept-Language: ar` for Arabic).
- **Themes at runtime**: the system app applies the workspace's theme (`shared/frontend/src/lib/theme.ts`):
  tokens become CSS variables on `html[data-theme="workspace"]`, plus `@font-face`, radius,
  shadows and `data-motion`. Printed invoices use its brand colour.

