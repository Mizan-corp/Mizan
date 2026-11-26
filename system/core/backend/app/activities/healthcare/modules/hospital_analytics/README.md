# HLT-24 — المؤشرات والذكاء السريري (BI) (Clinical Analytics & Business Intelligence) (planned)

## Overview
نسبة إشغال الأسرة (BOR)، متوسط مدة الإقامة (ALOS)، إنتاجية الأطباء، ومؤشرات الجودة ومكافحة العدوى.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_analytics`
- **API Prefix**: `/api/healthcare/analytics`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
