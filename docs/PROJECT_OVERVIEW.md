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
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, PostgreSQL (Neon / Supabase with Row Level Security), Redis / Uvicorn.
- **Frontend:** React 19, Vite 6, TypeScript 5.8, Tailwind CSS v4, Base UI / Radix primitives, Lucide React, Recharts.
- **Architecture:** Hybrid modular monolith with pluggable business modules (`shared/backend/app/modules/<sector>/<module>`), deployed as three separate products: system (ERP), website, and admin. See ADR-003.
- **Security:** RLS multi-tenancy, JWT + httpOnly session cookies, granular RBAC + ABAC permissions, Break-Glass emergency clinical access, immutable audit logging.
- **Deployment:** Vercel (Production Frontend & Serverless API), Docker / Koyeb for long-running services.
