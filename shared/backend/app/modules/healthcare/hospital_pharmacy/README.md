# HLT-12 — الصيدلية الدوائية وصرف الروشتات (Hospital Pharmacy & Medication Management)

## Overview
دليل الأدوية والبدائل، صرف الروشتات الرقمية، تتبع الصلاحيات (FEFO)، وسجل الأدوية المراقبة.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_pharmacy`
- **API Prefix**: `/api/healthcare/pharmacy`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
