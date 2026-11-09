# ADR-003: Separate System, Website and Admin Products

## Status
Accepted (2026-11-09)

## Context
The ERP, the marketing site with self-serve onboarding, and the Admoon control plane
were one frontend bundle and one API. Every customer downloaded the admin panel's
code and could read its endpoint map; a marketing copy change redeployed the ERP;
and the admin, website and ERP sessions shared one origin and one cookie jar.

## Decision
Split the repository into three products, each with its own frontend and backend,
deployed as separate Vercel projects on separate domains, over a shared kernel:

- `system/` — the ERP (tenant-facing).
- `website/` — landing, pricing, docs, signup and onboarding.
- `admin/` — Admoon, for super-admins only.
- `shared/backend` — one installable Python package (`app`) with models, tenancy,
  auth, services and domain modules. Each service is `create_app(...)` plus the
  routers it owns. All three use the same PostgreSQL database and `SECRET_KEY`.
- `shared/frontend` — design kit, API client, stores, i18n and styles, consumed via
  npm workspaces and the `@/` alias.

Cross-app sign-in uses an explicit handoff: the website (after onboarding) and the
admin panel (impersonation) open the system app with the access token in the URL
fragment, which the system app consumes and strips on load. The website and admin
APIs do not set tenant session cookies.

## Consequences
- Customers never receive admin code; the admin API exposes only `/admoon`, `/auth`
  and `/billing`; the website API exposes only plans and signup.
- Each product builds and deploys independently (Vercel ignored-build-step per folder).
- One database means no data sync between services; schema changes are still made
  once, in `shared/backend`, and affect all three.
- Changing `shared/` rebuilds all products.
