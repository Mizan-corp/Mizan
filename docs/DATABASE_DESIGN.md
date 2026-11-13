# Mizan ERP — Database Design & Multi-Tenancy

## 1. Multi-Tenancy Architecture
Mizan enforces a hybrid, multi-layered isolation model to ensure that no tenant can ever read or mutate another tenant's records:

1. **Application-Layer Scoping** (`app/platform/tenancy/context.py`):
   - All tenant-owned models inherit `TenantScoped` (`tenant_id` UUID, references `tenants`, not null, indexed).
   - A `before_flush` hook stamps the bound workspace's `tenant_id` on new rows (and refuses a row carrying another one).
   - Every ORM select, update and delete gets `tenant_id = <bound workspace>` added (`with_loader_criteria`).

2. **Database-Layer Row-Level Security (RLS):**
   - RLS is enabled and forced on every workspace table: `USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR current_setting('app.bypass', true) = 'on')`.
   - `bind_tenant` sets `app.tenant_id` for the transaction, and every later transaction of the session sets it again (`after_begin`).
   - While a workspace is bound, transactions run as the **`mizan_app`** role (`SET LOCAL ROLE`), which can't bypass RLS: the login role may (Neon's owner, a local superuser), so raw SQL is isolated too (#112). Request code never runs DDL or writes platform rows while bound.
   - Work that spans workspaces (the scheduler, cross-workspace lookups such as an installation token or a theme's font) turns `app.bypass` on for that transaction only, and off again before binding a workspace.

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

Besides the ERP's own records, every workspace has (all tenant-scoped, with RLS):

| Table | What it holds |
|---|---|
| `community_modules` | Developers' modules installed in the workspace (ADR-007): manifest, entities, approved scopes, the hash of the installation token, the webhook secret; key `(tenant_id, module_id)` |
| `ext_records` | Records of every community module's entities, as JSONB validated against the entity |
| `community_webhook_deliveries` | Webhooks to modules' servers: payload, status, attempts, next attempt, last error |
| `workspace_themes` | Theme packages installed in the workspace (ADR-010), with their font files; the chosen theme is `tenants.palette["name"]` |
| `workspace_files` | Every uploaded file and its size (#114) |

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
| `sys_roles` (`tenant_id IS NULL`) | The platform's standard roles and their permissions (workspaces' own roles have a `tenant_id`) |
| `revoked_tokens` | Signed-out sessions (by token id), until they would have expired anyway (#77) |
| `developer_users`, `developer_teams`, `developer_team_members` | The developer portal (ADR-007): developers (separate from owners), teams (a team's handle is its modules' namespace) and their members |
| `developer_keys` | Teams' signing keys and the certificates Mizan issued; `revoked_at` makes cloud installs refuse their packages |
| `developer_cli_tokens` | `mizan` CLI tokens (only their SHA-256) |

On site, the install's private PostgreSQL holds one workspace and the same schema; the
licence and installation identity live in files under the data folder
(`app.onprem.state`), not in these tables.

## 4. Migration Rules
- Database schema changes are tracked in `shared/backend/app/db/migrations.py` under the ordered `MIGRATIONS` list and applied with `python manage.py db migrate`.
- Every migration must be **strictly idempotent** (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).
- Migration runs execute statements sequentially with auto-healing and rollback safety.
- On-site installs run the same migrations during setup and on every repair/update, so migrations
  must also work on a fresh, single-workspace database.
- Production is migrated by the release workflow (`.github/workflows/deploy.yml`), before the new
  code is deployed: a migration must work with the code that's still running.
- **Models must match their migrations.** Local stacks, CI and on-site setup also create tables
  from the models (`create_all`) before migrations run, so a model declares the same primary key
  and database defaults (`server_default`, e.g. `gen_random_uuid()`) as its migration; otherwise
  those databases differ from production.
- Platform tables (no `tenant_id`) are written only outside a bound workspace (#112).
