# HLT-06 — الكشف الطبي ومسار الاستشارة (Consultation & Clinical Workflow) (planned)

## Overview
توثيق الكشف السريري (SOAP)، الشكوى الحالية، التشخيص (ICD-10)، الوصفات والطلبات الطبية.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_consultation`
- **API Prefix**: `/api/healthcare/consultations`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
