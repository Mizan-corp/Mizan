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

## 3. Platform Tables (not tenant-scoped)

These belong to Mizan itself, not to a workspace, and have no RLS policy. Only the owner,
admin and website APIs (and the system API's sign-in) read them.

| Table | What it holds |
|---|---|
| `tenants` | Every workspace: slug, sector, plan, limits, trial/paid-until, status, `deployment_mode` (`cloud_saas`, `desktop`, `lan`) |
| `owner_accounts` | Business owners (ADR-004): one owner, many workspaces; their own credentials |
| `tenant_billing_invoices` | Subscription invoices per workspace |
| `payment_transactions` | Paymob transactions, one per callback, idempotent on Paymob's id |
| `licences` | One per single-device/LAN workspace (ADR-005): mode, `valid_until` (extended on payment), `revoked_at` |
| `installations` | Each on-site install that checked in: host name, OS, version, last IP, last backup, first/last seen |
| `platform_audit_logs` | Every change made in the admin panel |

On site, the install's private PostgreSQL holds one workspace and the same schema; the
licence and installation identity live in files under the data folder
(`app.onprem.state`), not in these tables.

## 4. Migration Rules
- Database schema changes are tracked in `shared/backend/app/db/migrations.py` under the ordered `MIGRATIONS` list and applied with `python manage.py db migrate`.
- Every migration must be **strictly idempotent** (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).
- Migration runs execute statements sequentially with auto-healing and rollback safety.
- On-site installs run the same migrations during setup and on every repair/update, so migrations
  must also work on a fresh, single-workspace database.
- Production migrations are applied by hand before pushing the code that needs them (backup first).
