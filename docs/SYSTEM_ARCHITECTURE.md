# Mizan ERP — System Architecture

## 1. Architectural Style
Mizan is built as a **Modular Monolith** optimized for developer velocity, transaction integrity, and deployment simplicity:
- **Shared Enterprise Kernel:** Multi-tenancy resolution, database session lifecycle, audit logging, security context, and notification dispatch.
- **Pluggable Domain Modules:** Encapsulated in `shared/backend/app/modules/<domain>/` (models, routers, services) with screens in `system/frontend/src/modules/<domain>/`.

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
                    │   PostgreSQL (Neon / RLS GUC)   │
                    │   - Tenant Isolation Policies   │
                    │   - Immutable Audit Log Table   │
                    └─────────────────────────────────┘
```

## 2. Directory Layout

Mizan ships as **four products that are developed and deployed separately**, on top
of one shared kernel and one PostgreSQL database (see `docs/decisions/ADR-003-separate-apps.md` and `ADR-004-owner-accounts-and-payments.md`).

| Folder | What it is | Frontend | Backend |
|---|---|---|---|
| `system/` | The ERP tenants use every day | `system/frontend` → mizan-co-app | `system/backend` → mizan-co-api |
| `website/` | Landing, pricing, docs, signup, onboarding | `website/frontend` → mizan-co | `website/backend` → mizan-co-web-api |
| `owner/` | The owner panel: an owner's workspaces, subscriptions, Paymob payments (Arabic) | `owner/frontend` → mizan-co-owner | `owner/backend` → mizan-co-owner-api |
| `admin/` | The admin panel (English, Mizan team only) | `admin/frontend` → mizan-co-admin | `admin/backend` → mizan-co-admin-api |
| `shared/` | Code every product uses | `shared/frontend` (design kit) | `shared/backend` (domain kernel) |

- `shared/backend/` — installable Python package `app` (`mizan-shared`):
  - `app/factory.py`: builds every service (middleware, CORS, CSRF, errors, health).
  - `core/`: config, tenancy (ORM filter + RLS GUC), security, RBAC, sectors & plans, `printing/` (print engine).
  - `models/`, `schemas/`, `services/`, `db/` (engine + tracked SQL migrations in `db/sql/`).
  - `api/routers/`: the ERP endpoint library (mounted by the system service).
  - `modules/`: domain modules (models, routers, manifests, print templates).
- `system/backend/`: `main.py` + `system_api/` (route list, tenant resolution, tenant-side platform endpoints).
- `website/backend/`: `main.py` + `website_api/` (plans, self-serve signup).
- `owner/backend/`: `main.py` + `owner_api/` (account, workspaces, billing and the Paymob callback).
- `admin/backend/`: `main.py` + `admin_api/` (one router per page: overview, workspaces, billing, activity, team, system).
- `shared/frontend/src/`: kit components, API client, auth/UI stores, i18n, styles, plans, pricing page, cross-app URLs and session handoff.
- `system/frontend/src/`: app shell, ERP features, tenant routing, and `modules/` (industry screens).
- `website/frontend/src/`: marketing pages and the docs portal.
- `owner/frontend/src/`: the owner panel pages and the welcome tour.
- `admin/frontend/src/`: the admin panel pages.
- `docs/`: System documentation, architecture decision records, and API specs.
- `.agents/`: Antigravity engineering rules and procedural skills.

Import aliases (frontends): `@/` is the shared kit, `@app/` is the current app, `@modules/` (system only) is the industry screens.
