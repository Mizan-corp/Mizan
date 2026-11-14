# HLT-13 — إدارة الطوارئ والفرز (ER Triage) (Emergency Department & Triage Management) (planned)

## Overview
استقبال الطوارئ، تصنيف خطورة الحالات (ESI 1-5)، مسارات الإنعاش السريع، وتسكين أسرة الطوارئ.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_emergency`
- **API Prefix**: `/api/healthcare/emergency`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
