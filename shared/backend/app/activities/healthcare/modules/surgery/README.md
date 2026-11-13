# HLT-14 — العمليات الجراحية وغرف العمليات (OT) (Operating Room & Surgery Management)

## Overview
جدولة غرف العمليات، الفريق الجراحي والتخدير، قائمة التحقق الجراحية (WHO)، وغرفة الإفاقة.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_surgery`
- **API Prefix**: `/api/healthcare/surgery`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
