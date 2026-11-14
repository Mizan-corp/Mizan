# HLT-17 — المستودعات الطبية والمشتريات (Medical Inventory & Procurement) (planned)

## Overview
المستلزمات الطبية، أدوات الجراحة، تتبع التشغيلات والصلاحيات، طلبات الشراء، وأرصدة الأقسام.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_inventory_procurement`
- **API Prefix**: `/api/healthcare/inventory`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
