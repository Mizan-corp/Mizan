# Mizan ERP — System Architecture

## 1. Architectural Style
Mizan is built as a **Modular Monolith** optimized for developer velocity, transaction integrity, and deployment simplicity:
- **Shared Enterprise Kernel:** Multi-tenancy resolution, database session lifecycle, audit logging, security context, and notification dispatch.
- **Pluggable Domain Modules:** Encapsulated in `backend/app/modules/<domain>/` with self-contained API routers, schemas, service logic, and frontend components.

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
- `backend/app/`: Core backend application.
  - `core/`: Config, database engine, async session handlers, security helpers.
  - `models/`: Central enterprise models (User, Tenant, Organization, Membership, AuditLog).
  - `api/routers/`: Global endpoints (Auth, Tenants, Health, System).
  - `modules/`: Standalone domain modules (`healthcare/`, `hospitality/`, `pos/`, `wholesale/`, etc.).
- `frontend/`: Single Page Application (SPA).
  - `src/components/`: Reusable primitive components (Base UI / Radix primitives + Tailwind).
  - `src/features/`: Top-level marketing, authentication, and core tenant routes.
  - `src/lib/`: API client (`api.ts`), navigation routing (`nav.ts`), formatters, and utilities.
  - `src/stores/`: Zustand state management (Auth, Tenant, UI theme, active modules).
- `docs/`: System documentation, architecture decision records, and API specs.
- `.agents/`: Antigravity engineering rules and procedural skills.
