# HLT-11 — الأشعة والتصوير الطبي (RIS/PACS) (Radiology & Imaging Management (RIS/PACS))

## Overview
طلبات الأشعة (X-Ray, CT, MRI, US)، أجهزة التصوير، تقارير أطباء الأشعة، وحالة الفحوصات.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_radiology`
- **API Prefix**: `/api/healthcare/radiology`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
