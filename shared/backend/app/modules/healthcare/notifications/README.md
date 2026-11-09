# HLT-23 — الإشعارات والتنبيهات الطبية (Healthcare Notifications & Alerts)

## Overview
تذكير المواعيد عبر SMS/واتساب، تنبيهات النتائج المخبرية الحرجة، استدعاء الأطباء، وإشعارات الفواتير.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_notifications`
- **API Prefix**: `/api/healthcare/notifications`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
