# HLT-02 — تسجيل وهوية المرضى (MPI) (Patient Registration & Master Patient Index)

## Overview
ملفات المرضى، الرقم الطبي الموحد (MRN)، الهوية الوطنية، فحص الازدواجية، ودمج السجلات.

## Architecture & Integration Boundaries
- **Domain**: Healthcare / Hospital ERP
- **Module ID**: `hlt_patient_identity`
- **API Prefix**: `/api/healthcare/patients`
- **PostgreSQL Row Level Security (RLS)**: Enforced via `TenantScoped, Base`
- **Frontend View**: `frontend/index.tsx` (Warm Editorial Luxury tokens)
