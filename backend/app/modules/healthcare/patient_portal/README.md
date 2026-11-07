# HLT-21 — بوابة المريض والخدمات الرقمية (Patient Portal & Digital Services)

## Overview
حسابات المرضى، حجز المواعيد الذاتي، استعراض نتائج التحاليل والأشعة، وسجل الوصفات والتقارير.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_patient_portal`
- **API Prefix**: `/api/healthcare/portal`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
