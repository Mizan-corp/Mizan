# HLT-15 — الفوترة الطبية وحسابات المرضى (Billing, Invoicing & Patient Accounts) (planned)

## Overview
تسعيرة الخدمات، فواتير الكشوفات والإجراءات، حساب نسبة التحمل، سندات القبض، ودفعات المرضى.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_billing`
- **API Prefix**: `/api/healthcare/billing`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
