# HLT-05 — السجل الطبي الإلكتروني التراكمي (Longitudinal Electronic Medical Records (EMR)) (planned)

## Overview
العلامات الحيوية، التاريخ المرضي والجراحي، الحساسيات الدوائية، الأمراض المزمنة، والمرفقات.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_emr`
- **API Prefix**: `/api/healthcare/emr`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
