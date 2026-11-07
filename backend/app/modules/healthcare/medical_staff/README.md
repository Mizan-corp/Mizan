# HLT-04 — الأطباء والكوادر الطبية (Doctor & Medical Staff Management)

## Overview
ملفات الأطباء، التخصصات، التراخيص المهنية، بدلات الكشفية، وجداول المناوبات والورديات.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_medical_staff`
- **API Prefix**: `/api/healthcare/medical-staff`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
