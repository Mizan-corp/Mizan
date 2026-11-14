# HLT-01 — إدارة المنشآت والمرافق الصحية (Healthcare Facility & Organization Management) (planned)

## Overview
إدارة المنشآت الطبية، المستشفيات، الفروع، الأقسام، العيادات، وساعات العمل والاعتمادات.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_facility_management`
- **API Prefix**: `/api/healthcare/facilities`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
