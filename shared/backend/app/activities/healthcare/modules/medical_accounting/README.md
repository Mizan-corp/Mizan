# HLT-18 — المحاسبة الطبية ومراكز التكلفة (Accounting & Healthcare Financial Management) (planned)

## Overview
مراكز تكلفة الأقسام، عمولات وأتعاب الأطباء، إيرادات العيادات والأجنحة، وقيود اليومية التلقائية.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_accounting`
- **API Prefix**: `/api/healthcare/accounting`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
