# Mizan ERP — Project Overview

## 1. What is Mizan?
**Mizan (ميزان)** is a cloud-native, multi-tenant enterprise resource planning (ERP) platform designed specifically for emerging and regulated markets, starting with Egypt and the MENA region. 

It unifies commercial, clinical, industrial, and administrative operations into a single cohesive, high-performance web suite with native Arabic (RTL) typography, deep localization (Egyptian Tax Authority e-Invoicing, GAHAR & MOH healthcare standards, multi-currency support with EGP default), and rigorous multi-tenancy isolation.

## 2. Core Business Sectors
Mizan serves specialized verticals through dedicated sector modules while maintaining a shared enterprise core:
1. **Healthcare & Hospitals (الرعاية الصحية والمستشفيات):** Clinics, Specialized Medical Centers, General & Surgical Hospitals, Diagnostic Labs, Pharmacies, Radiology Centers.
2. **Retail & Point of Sale (التجزئة ونقاط البيع):** Multi-branch POS, barcode scanning, cashier shifts, promotions.
3. **Wholesale & Distribution (تجارة الجملة والتوزيع):** Tiered pricing, credit limits, dispatch logistics.
4. **Hospitality & Hotels (الفنادق والضيافة):** PMS, room bookings, housekeeping, minibar billing.
5. **Manufacturing & Industrial (التصنيع والإنتاج):** BOM, work orders, discrete & process manufacturing.
6. **Professional Services (الخدمات المهنية والشركات):** Project billing, time-tracking, client retainers.

## 3. Technology Stack Summary
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, PostgreSQL 16 (Neon in the cloud, bundled on site) with Row Level Security, Uvicorn.
- **Frontend:** React 19, Vite 6, TypeScript 5.8, Tailwind CSS v4, Base UI / Radix primitives, Lucide React, Recharts.
- **Architecture:** Hybrid modular monolith. Each business activity is one folder of modules, variants, themes and demo data (`shared/backend/app/activities/<activity>/`, ADR-006, ADR-010), deployed as four separate products: system (ERP), website, owner panel and admin panel, plus on-site installers. See ADR-003, ADR-004 and ADR-005.
- **Extension platform:** outside developers build declarative community modules, theme packs and whole business activities with the same framework, signed and installed per workspace, with a developer portal and docs at dev.allmizan.live and the `mizan` CLI (ADR-007, ADR-010).
- **Security:** RLS multi-tenancy (queries as a role that can't bypass it), JWT sessions with revocation, permissions declared by modules and held by roles, clinical records behind clinical roles, signed packages, audit logging.
- **Deployment:** Vercel (frontends and serverless APIs) on `allmizan.live` with Neon PostgreSQL for the cloud, released by CI after migrating the database. Workspaces can instead run on site, on one computer or as a server on the shop's network, installed by Mizan Setup for Windows and Linux with a bundled PostgreSQL and an offline, signed licence (ADR-005, `installer/`). Docker Compose for local development.
