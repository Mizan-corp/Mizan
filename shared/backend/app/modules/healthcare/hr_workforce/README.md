# HLT-19 — الموارد البشرية والامتيازات السريرية (HR & Clinical Workforce Management)

## Overview
تراخيص المزاولة الطبية، الامتيازات السريرية، ساعات التعليم الطبي المستمر (CME)، وتبادل الورديات.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_hr_workforce`
- **API Prefix**: `/api/healthcare/hr`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
