# Mizan ERP — Database Design & Multi-Tenancy

## 1. Multi-Tenancy Architecture
Mizan enforces a hybrid, multi-layered isolation model to ensure that no tenant can ever read or mutate another tenant's records:

1. **Application-Layer Scoping:**
   - All tenant-owned models inherit from `TenantScoped` base model (`tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False, index=True)`).
   - SQLAlchemy `before_flush` hook automatically injects the active request's `tenant_id` from Python context vars into newly created models.
   - All repository queries automatically include `.filter_by(tenant_id=current_tenant_id)`.

2. **Database-Layer Row-Level Security (RLS):**
   - PostgreSQL RLS is enabled on all business tables (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`).
   - Tenant isolation policy: `USING (tenant_id = current_setting('app.tenant_id', true)::uuid)`.
   - On every checkout of a database connection from the pool, FastAPI middleware runs `SET LOCAL app.tenant_id = '<uuid>'`.
   - Superuser or migration tasks bypass RLS via `SET LOCAL app.bypass = 'on'`.

## 2. Core Entity Relationship Overview

```
[Tenants] 1 ─── N [HealthcareOrganizations]
                       │ 1
                       ├─── N [Facilities / Hospitals]
                       │         │ 1
                       │         ├─── N [Buildings] ─── N [Floors] ─── N [Rooms/Beds]
                       │         └─── N [Departments] ─── N [Units] ─── N [ServiceLocations]
                       │
                       └─── N [Patients (Master Patient Index)]
                                 │ 1
                                 ├─── N [Appointments]
                                 ├─── N [Clinical Encounters (EMR)]
                                 ├─── N [Lab Orders]
                                 ├─── N [Prescriptions]
                                 └─── N [Inpatient Admissions]
```

## 3. Migration Rules
- Database schema changes are tracked in `scripts/migrate.py` under the ordered `MIGRATIONS` tuple.
- Every migration must be **strictly idempotent** (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).
- Migration runs execute statements sequentially with auto-healing and rollback safety.
