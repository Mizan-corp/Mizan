# HLT-20 — الأجهزة الطبية والمعايرة الحيوية (Medical Equipment & Maintenance Management)

## Overview
سجل الأجهزة الطبية، الصيانة الوقائية، شهادات المعايرة الدورية، وتذاكر الأعطال والإصلاح.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_equipment_maintenance`
- **API Prefix**: `/api/healthcare/equipment`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
