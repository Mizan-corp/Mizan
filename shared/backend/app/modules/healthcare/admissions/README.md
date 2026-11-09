# HLT-07 — التنويم والإدخال والخروج (ADT) (Inpatient Admission & Discharge Management)

## Overview
أوامر التنويم، تسكين الأسرة، تحويلات الأجنحة، ملخصات الخروج، ومتابعة الإقامة السريرية.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_admissions`
- **API Prefix**: `/api/healthcare/admissions`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
