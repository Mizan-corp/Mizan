# HLT-16 — التأمين الطبي والمطالبات (Insurance & Claims Management)

## Overview
شركات التأمين، بوالص المرضى، الموافقات المسبقة، تقديم المطالبات الإلكترونية، والتسوية والرفض.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_insurance`
- **API Prefix**: `/api/healthcare/insurance`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
