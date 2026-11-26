# HLT-10 — إدارة المختبرات والتحاليل (LIS) (Laboratory Information Management (LIS)) (planned)

## Overview
دليل الفحوصات، باركود العينات، النتائج المخبرية، المعدلات الطبيعية، والتنبيه بالقيم الحرجة.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_laboratory`
- **API Prefix**: `/api/healthcare/laboratory`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
