# HLT-03 — المواعيد وجدولة الأطباء (Appointment & Scheduling Management) (planned)

## Overview
حجز المواعيد، جداول الأطباء، منع التعارض، قوائم الانتظار، وإدارة دور الانتظار اللحظي.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_appointments`
- **API Prefix**: `/api/healthcare/appointments`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
