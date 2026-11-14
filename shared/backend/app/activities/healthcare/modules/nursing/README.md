# HLT-09 — التمريض وسجل إعطاء الأدوية (MAR) (Nursing Care & Medication Administration) (planned)

## Overview
خطة الرعاية التمريضية، سجل إعطاء الدواء (MAR)، توازن السوائل، وتقارير تسليم الورديات.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_nursing`
- **API Prefix**: `/api/healthcare/nursing`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
