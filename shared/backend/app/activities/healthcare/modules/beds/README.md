# HLT-08 — إدارة الأسرة والأجنحة والغرف (Bed, Ward & Room Management)

## Overview
مخطط الأجنحة، حالة الأسرة اللحظية (شاغر، مشغول، تعقيم، صيانة)، وتسعيرة الإقامة اليومية.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_beds`
- **API Prefix**: `/api/healthcare/beds`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
