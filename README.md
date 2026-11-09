<div align="center">

<img src="frontend/public/icon.svg" width="88" alt="Mizan" />

# ميزان · Mizan

### أدر أعمالك بتوازن.
**One system for every kind of business.**

An Arabic-first, multi-tenant ERP that shapes itself around the business using it,
whether that's a corner shop, a restaurant, a pharmacy, a hotel or a factory.

[![CI/CD](https://github.com/ammar0xff/Mizan/actions/workflows/ci.yml/badge.svg)](https://github.com/ammar0xff/Mizan/actions/workflows/ci.yml)
&nbsp;![RTL](https://img.shields.io/badge/Arabic-RTL%20first-651E2C)
&nbsp;![Stack](https://img.shields.io/badge/FastAPI%20·%20React%2019%20·%20PostgreSQL-262321)

[**Open the app →**](https://mizan-co.vercel.app) &nbsp;·&nbsp;
[API docs](https://mizan-co-api.vercel.app/api/docs) &nbsp;·&nbsp;
[Documentation](docs/)

</div>

---

## What is Mizan?

*Mizan* (ميزان) is Arabic for **balance**, the scale a merchant uses to weigh goods fairly.
The product is built on the same idea: everything a business does (selling, stocking, buying,
paying people, keeping the books) recorded in **one balanced system** instead of spreadsheets,
paper ledgers and disconnected cash registers.

It is built **for Egypt first**: Arabic interface, Egyptian pound, Cairo time, 14% VAT,
Egyptian payroll law, Vodafone Cash / InstaPay wallets and thermal receipts with tax QR codes.

## How it works: three questions

```
  ① What does your business do?     →  pharmacy, restaurant, retail, clinic, factory …
  ② How big is it?                  →  one shop, a few branches, an enterprise
  ③ What should it look like?       →  your brand colour, your logo, the features you want
                                       ↓
          Your own workspace, already filled with realistic demo data
          for your sector. Free for 14 days.
```

The chosen **business activity** is the key. It decides which modules switch on, what the
screens look like, and how you work in them. The point-of-sale module, for example:

| A restaurant sees | A retail shop sees | A pharmacy sees |
|---|---|---|
| a floor plan, open tickets, a kitchen display | a two-pane checkout, barcode + numpad, `F2` `F3` `Esc` | a search-first drug list, batch expiry colours, substitutes |

Same engine, same data, **a different tool for every trade.**

---

## Everything in one place

### The shared core: every workspace gets this

| | |
|---|---|
| 🧾 **Point of sale** | Barcode scanning, retail/wholesale prices, credit sales with limits, split payments, hold & resume, cashier shifts, **works offline** and syncs later |
| 📄 **Sales** | Invoices, quotations → invoices, partial and full returns, branded Arabic PDF invoices, Excel export |
| 📦 **Inventory** | Multi-warehouse stock, transfers, stocktaking, adjustments, reorder levels with low-stock alerts |
| 🛒 **Purchasing** | Supplier invoices, purchase orders and receiving, price history, supplier statements |
| 👥 **Customers & suppliers** | Running balances, credit limits, statements, collections |
| 💰 **Finance** | Cash safes, e-wallets, expenses, general ledger, trial balance, journal vouchers, monthly period close |
| 🧑‍💼 **HR & payroll** | Employees, attendance (CSV or ZKTeco fingerprint devices), payroll run draft → review → approve → pay, payslips |
| 📊 **Reports** | Sales, stock, cash flow, debt aging, and a dashboard built around *today's sales* |
| 🔔 **Everyday comfort** | Notification centre, `Ctrl+K` command palette, light/dark mode, Arabic ⇄ English switch, installable as an app (PWA) |

### Industry modules: switched on by your activity

Mizan's long-term map covers **30 business types**. Each one is a self-contained module
that plugs into the shared core.

| Family | Modules |
|---|---|
| **Shops & dining** | Retail POS · Supermarket fast-scan · Restaurant & café · Kitchen display (KDS) · Pharmacy |
| **Distribution** | Wholesale · Logistics & fleet · 3PL warehousing (WMS) · E-commerce · Online storefront |
| **Services** | Clinic & hospital · Law firm · Travel agency · Hotel (PMS) · Gym · Salon & spa · Creative/translation agency · Field service · School · Professional services |
| **Manufacturing** | Discrete assembly · Food & beverage (HACCP) · Pharmaceutical (GMP) · Printing & packaging |
| **Projects & land** | Construction · Real estate · Agriculture · Energy & power plants |
| **Specialised** | Banking · Insurance · Government & NGOs · Entertainment & events · Oil & gas |
| **Connectors** | WhatsApp Business receipts · ZKTeco attendance · Thermal printers & barcode scanners |

> **Honest status.** The core and the Shops & dining family are the most mature. Most other
> industry modules are **scaffolded**: their data, API and screens exist, but depth varies from
> module to module. See [Where things stand](#where-things-stand).

---

## Plans

| | Trial | Starter | Pro | Enterprise |
|---|:---:|:---:|:---:|:---:|
| **Price / month** | Free · 14 days | 450 EGP | 850 EGP | 1,950 EGP |
| **Price / year** | — | 4,500 EGP | 8,500 EGP | 19,500 EGP |
| **Users** | 3 | 5 | 15 | Unlimited |
| **Branches** | 1 | 1 | 3 | Unlimited |
| **Sales invoices / month** | 100 | 500 | 5,000 | Unlimited |
| **Industries** | Core | Core + Phase 1 | Phases 1–3 | All 30 |

Prices come from `backend/app/core/plans.py`, which is the source of truth.

---

## Under the hood

```mermaid
flowchart TB
    subgraph Clients
        A[Web app · React 19<br/>Arabic RTL · PWA · offline POS]
        S[Public storefronts]
    end
    subgraph API["FastAPI (one modular monolith)"]
        M[Auth · tenant resolver · RBAC/ABAC · audit]
        C[Shared core<br/>POS · sales · stock · finance · HR]
        V[48 pluggable modules<br/>one manifest each]
        AD[Admoon<br/>platform control plane]
    end
    DB[(PostgreSQL 16<br/>Row-Level Security)]
    A --> M
    S --> M
    M --> C & V & AD
    C & V & AD --> DB
```

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · Pydantic v2 · PostgreSQL 16 (Neon) |
| **Frontend** | React 19 · TypeScript (strict) · Vite · Tailwind CSS v4 · shadcn/ui on Base UI · TanStack Query · Zustand · Motion · Recharts |
| **Hosting** | Vercel (app + API) · Neon (database) · Docker Compose for local and on-premise |

### Four ideas that hold it together

**1. Every business is sealed off from every other.**
Each row carries a `tenant_id`, and isolation is enforced three times: an automatic ORM
filter, automatic stamping on insert, and **PostgreSQL Row-Level Security** as a final wall
inside the database. If an application bug forgets a filter, the database still says no.

**2. Modules are plug-ins, not forks.**
Every module is a folder (`modules/<id>/`) with a `manifest.json` (category, dependencies,
permissions, business types), its own models, API router and screens. The marketplace at
`/modules` turns them on and off per workspace, and every route is guarded by `require_module`.

**3. Permissions mirror real jobs.**
Mizan separates **positions** (what someone does: pharmacist, cashier, chief accountant;
98 are catalogued), **account types** (their licence tier) and **permissions**
(`scope:action` tokens). Clinical records are fenced off from non-clinical staff, and a
logged, time-limited **break-glass** override exists for emergencies.

**4. Money is treated like money.**
Amounts are stored as exact decimals, never floats. Postings are atomic. Financial records
are never hard-deleted, and every destructive action leaves an audit trail.

### Admoon: the control plane

Admoon (`/admoon`) is where the platform owner runs Mizan itself: creating and provisioning
workspaces, plans and subscriptions, MRR, resource metrics, backups, provisioning jobs and
platform audit logs. Access is limited to super-admins.

---

## Design

Mizan is designed for people who sit in it **eight to twelve hours a day**, so it aims to be
calm, dense and fast, not flashy.

- **Look: warm editorial.** Oxblood `#651E2C`, Deep Merlot `#35151D`, Warm Ivory `#F5EBDD`,
  Charcoal `#262321`. Each workspace can re-tint the brand colour; status colours never change meaning.
- **Type:** IBM Plex Sans Arabic for the interface, Manrope for Latin text. Numbers are always
  Western digits in tabular alignment (`ar-EG-u-nu-latn`).
- **Composition: «دفتر اليوم», the daily ledger.** Screens read like a merchant's ledger page,
  not a generic admin template: one dominant figure, open ruled tables, status as a dot and a word.
- **Every screen has five states** (loading, empty, error, no-permission, full) and one clear primary action.
- **Accessibility target:** WCAG 2.2 AA, full keyboard use, and respect for *reduce motion*.

The full canon lives in [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md),
[`docs/UI_UX_GUIDELINES.md`](docs/UI_UX_GUIDELINES.md) and [`docs/ui-ux-kit/`](docs/ui-ux-kit/).

---

## Where things stand

| Status | What |
|---|---|
| ✅ **Live** | Multi-tenant SaaS · self-serve signup & onboarding · POS (online + offline) · sales · inventory · purchasing · customers & suppliers · finance & ledger · HR & payroll · reports · notifications · storefront · thermal printing & barcode scanning · ZKTeco sync · Arabic/English · Admoon panel · plan limits |
| 🧱 **Working, being deepened** | Restaurant & kitchen display · pharmacy · clinic (billing, clinical roles, FEFO dispensing, claims) · hotel PMS · school · gym · salon · wholesale |
| 🪴 **Scaffolded** | Manufacturing, projects, specialised and remaining service modules: models, API and screens exist, with workflows still to be filled in |
| 🔌 **In progress** | WhatsApp receipts (configured and logged; live sending queued) · online payment gateways (Paymob / Fawry webhook exists; production wiring pending) |
| 🗺️ **Planned** | Egyptian Tax Authority e-invoicing · loyalty points · desktop, LAN and bring-your-own-database deployment modes · full hospital suite (EMR, inpatient, radiology, theatre) |

The roadmap lives in [`TASKS.md`](TASKS.md) and [`docs/DEVELOPMENT_ROADMAP.md`](docs/DEVELOPMENT_ROADMAP.md).
Independent audits, and what was fixed after them, live in [`docs/audit/`](docs/audit/).

---

## Run it locally

**Requirements:** Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
# 1 · database (Postgres on :5433) and backend
docker compose up -d

# 2 · apply migrations (idempotent, safe to re-run)
python3 scripts/migrate.py

# 3 · frontend on http://localhost:5173 (calls to /api are proxied)
cd frontend && npm install && npm run dev
```

Running the backend outside Docker:

```bash
cd backend && .venv/bin/uvicorn main:app --port 8010
```

A fresh database creates a first admin account. Change its password immediately.

### Tests

```bash
cd frontend && npm test && npm run build        # unit tests + strict type-check + build
cd backend  && .venv/bin/pytest -q              # backend tests (security, accounting, clinic)
cd e2e && E2E_API_BASE=http://localhost:8000 \
  E2E_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/inventory_db \
  .venv/bin/pytest -q                           # live API suite. Both URLs must point at the same server
```

CI runs lint, the frontend build, unit tests and the full Docker-based end-to-end suite on every push.

---

## Repository map

```
backend/
  app/api/routers/   core API: auth, POS, sales, stock, purchases, finance, HR, billing, admoon …
  app/core/          config, security, tenancy, plans
  app/modules/       industry & integration modules (backend side)
  migrations/        SQL used by tracked migrations
modules/             module manifests + categories.json (the 30-industry registry)
frontend/src/
  features/          app screens, marketing site, onboarding, admoon
  components/kit/    shadcn/ui components (owned, editable)
  components/app/    PageHeader, ListState, TableShell, StatCard …
engines/printing/    receipt & document printing engine
e2e/                 live API end-to-end suite
scripts/             migrate.py, seeders, verification scripts
docs/                product, architecture, design, security and requirements docs
```

## Documentation

| Start here | Then |
|---|---|
| [Project overview](docs/PROJECT_OVERVIEW.md) | [Requirements (SRS)](docs/developer/mizan/srs/SRS-Mizan-v1.0.md) · [30-industry specs](docs/srs/00_MASTER_INDEX.md) |
| [System architecture](docs/SYSTEM_ARCHITECTURE.md) | [ADRs](docs/decisions/) · [Database & tenancy](docs/DATABASE_DESIGN.md) · [API standards](docs/API_STANDARDS.md) |
| [Security standards](docs/SECURITY_STANDARDS.md) | [Roles & permissions](docs/USER_ROLES_AND_PERMISSIONS.md) |
| [Design system](docs/DESIGN_SYSTEM.md) | [UI/UX kit](docs/ui-ux-kit/) · [Brand identity](docs/developer/mizan/frontend/08-brand-identity-full.md) |
| [Engineering standards](docs/ENGINEERING_STANDARDS.md) | [Contributor & agent rules](AGENTS.md) |

---

<div align="center">

**ميزان**: نظام واحد. رؤية أوضح. نمو أذكى.

<sub>Made in Egypt · Private repository · All rights reserved</sub>

</div>
