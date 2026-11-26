# HLT-22 — الطب الاتصالي والاستشارات المرئية (Telemedicine & Virtual Consultations) (planned)

## Overview
جلسات الفيديو المشفرة، غرف الانتظار الافتراضية، التوثيق السريري عن بعد، والروشتات الرقمية.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_telemedicine`
- **API Prefix**: `/api/healthcare/telemedicine`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
