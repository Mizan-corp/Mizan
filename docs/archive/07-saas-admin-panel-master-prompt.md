> **Archived (2026-11-12): historical, not current.** This describes the earlier "Admoon" control plane and billing. Today: the admin panel (`admin/README.md`), the owner panel and Paymob billing (`owner/README.md`), and the decisions in `docs/decisions/` (ADR-003 separate apps, ADR-004 owner accounts and payments, ADR-005 deployment modes, ADR-008 one domain).

# Mizan — SaaS Admin Panel Master Prompt (Admoon)
Source: ChatGPT Main chat, message [3], Nov 2026 (gpt-6)
This is the full master prompt for building the multi-tenant SaaS administration panel.

---

## Purpose
Build a production-oriented **Multi-Tenant SaaS Administration Panel** (Admoon) that allows creation, configuration, deployment, monitoring, and management of ERP tenants independently.

Not just a user/subscription manager — a full **Tenant Provisioning and Infrastructure Management System**.

---

## Core Architectural Principle

Clear separation between:
1. **SaaS Control Plane** — manages tenants, configs, licenses, subscriptions, deployments, monitoring
2. **Tenant Management Layer** — tenant-specific configuration and state
3. **Tenant ERP Application** — the business ERP modules
4. **Infrastructure and Deployment Layer** — actual infrastructure provisioning
5. **Storage and Backup Layer** — file storage and backup management

The control-plane database must be **independent** of tenant databases.

---

## Technology Stack

### Frontend
- React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- React Router + TanStack Query + React Hook Form + Zod + Recharts

### Backend
- Node.js + TypeScript + NestJS (or equivalent modular framework)
- REST API + OpenAPI/Swagger + background job processing

### Database
- PostgreSQL for central control-plane (independent of tenant DBs)
- Prisma ORM
- Redis for caching, distributed locks, job coordination

### Infrastructure
- Docker + Docker Compose
- S3-compatible storage abstraction
- Automated database migration system
- Background provisioning worker

---

## Tenant Data Model

Each tenant has:
- Unique tenant ID, business name, legal name, slug
- Business type, industry, country, timezone, language, currency
- Tax configuration, tenant owner, contact email/phone
- Subscription plan and status
- Created date, last activity
- Deployment configuration, database configuration, storage configuration
- Enabled ERP modules

### Tenant statuses
`Pending → Provisioning → Active → Suspended → Maintenance → Failed → Archived`

### Tenant operations
- Create, edit, view, suspend, reactivate, archive, delete (with explicit confirmation)
- Clone configuration, reset environment
- View activity, infrastructure, resource usage, deployment history

> **NEVER** delete tenant business data automatically when a subscription expires or tenant is suspended.

---

## Hosting Modes (Deployment Modes)

Mizan supports four deployment modes. Admoon manages tenants across all four.

### Mode 1 — Standalone Desktop
- Single executable (Electron or Tauri) with embedded database (SQLite or embedded PostgreSQL)
- No network required; single-user; fully offline
- License: embedded in app bundle; re-validates online when available
- Admoon visibility: last heartbeat snapshot only; no live metrics
- Updates: signed update bundles pushed by Admoon; applied on next launch

### Mode 2 — LAN Server (was "C. LAN Deployment")
- Full system on tenant's own server; accessible over local network
- Database: PostgreSQL on the same server
- License: validated against server hardware fingerprint; heartbeat every 7 days; 14-day offline grace
- Admoon visibility: via Deployment Agent (outbound HTTPS only)
- Updates: Agent-pushed package from Admoon

### Mode 3 — Bring Your Own Database (BYOD) (was "D. VPS Deployment")
- Frontend hosted by tenant (Vercel, Netlify, VPS, or Mizan CDN)
- Database: tenant-owned PostgreSQL, Neon, Supabase, or Firebase
- License: validated against database endpoint fingerprint
- Admoon visibility: via optional Deployment Agent
- Updates: container pull from Mizan registry

### Mode 4 — Fully Managed SaaS (was "A. Fully Hosted SaaS")
- Everything hosted and operated by Mizan
- Multi-tenant PostgreSQL with RLS on Neon
- License: enforced server-side by Admoon
- Admoon visibility: full direct access
- Cloud-hosted app, managed database, remote access, automated backups, SSL/TLS, automated updates

### Hosting config fields
`hosting_mode, provider, env_name, app_host, domain, port, internal_network_address, public_access, ssl_enabled, deployment_status, deployment_version, deployment_timestamp, last_health_check, resource_limits`

---

## Database Configuration

### Supported providers
| Provider | Notes |
|---|---|
| PostgreSQL (self-hosted/cloud/VPS) | Default for ERP |
| MySQL (self-hosted/VPS) | Alternative relational |
| Neon | Managed PostgreSQL — treat as PostgreSQL adapter |
| Firebase/Firestore | Distinct NoSQL provider, NOT a relational DB replacement |
| SQLite (local embedded) | Single-machine offline only |

### Tenancy models
- Shared database with tenant isolation (RLS)
- Separate database per tenant
- Separate database server per tenant
- Local embedded database

### Database operations
`test_connection, validate_config, provision_db, run_migrations, health_check, view_usage, view_size, view_connections, configure_backup, restore_backup, rotate_credentials, disconnect, change_provider (controlled migration, never silently overwrites data)`

> **NEVER** expose raw database passwords, credentials, or private keys in frontend responses, browser storage, logs, or URLs.

---

## Storage Configuration

### Supported providers
- **Local Storage**: filesystem path, max capacity, permissions, backup directory
- **S3-Compatible**: Amazon S3, Cloudflare R2, MinIO — endpoint, bucket, region, keys (by reference), encryption, versioning, lifecycle
- **Cloud Storage**: Firebase Storage, other adapters

### Storage categories
ERP documents, user uploads, product images, employee documents, customer attachments, invoices, reports, database backups, application logs, archived documents

### Storage features
Usage monitoring, quota, upload limits, health checks, retention policies, backup sync, versioning, migration, provider switching, access permissions

---

## Infrastructure Management

### Per tenant config
App server, database server, storage, cache, background worker, domain, SSL certs, network config, resource limits, deployment environment

### Resource limits per tenant
CPU, RAM, storage, DB size, max users, max concurrent sessions, API request limits, max upload size, background job limits

### Monitoring
CPU/RAM/disk usage, DB utilization, app response time, request throughput, error rate, active users, background job status, backup status, last health check

> For local/LAN tenants: use a lightweight **deployment agent** to collect metrics. The central panel CANNOT directly access private LAN machines.

---

## Tenant Provisioning Engine

Background workflow (must be idempotent, retryable, with progress tracking):

1. Create tenant record
2. Validate tenant configuration
3. Validate database configuration
4. Validate storage configuration
5. Provision required infrastructure
6. Initialize database
7. Run database migrations
8. Create initial tenant administrator
9. Assign subscription and entitlements
10. Enable selected ERP modules
11. Configure storage
12. Perform health checks
13. Activate tenant
14. Generate deployment report

> Never run long-running provisioning tasks inside HTTP request handlers.

---

## ERP Module Catalog

Each module has: module_id, name, description, version, dependencies, required_permissions, subscription_requirements, compatibility, installation_status

Example modules: Finance, Accounting, Inventory, Purchasing, Sales, CRM, HR, Payroll, POS, Pharmacy, Healthcare, Manufacturing, WMS, Logistics, Construction, Real Estate, Hotel Management, Education

Operations: enable, disable, view dependencies, view version, upgrade, check compatibility, view installation logs

> Do NOT enable a module when required dependencies are missing.

---

## Subscription and Billing

### Plans
Free / Starter / Professional / Business / Enterprise / Custom

### Per plan
Monthly and annual pricing, user limits, storage limits, DB limits, enabled modules, feature entitlements, support level, hosting eligibility, usage limits

### Operations
Create, change, upgrade, downgrade, renew, cancel, suspend subscription; manage trial; manage invoices; track payments; track overdue; usage reports

> Keep subscription enforcement separate from data deletion.

---

## Backup and Disaster Recovery

### Per tenant config
DB backup provider, file backup provider, backup frequency, retention period, encryption, destination, status, last successful, next scheduled, RPO, RTO

### Operations
Manual backup, schedule automatic, view history, verify integrity, restore, download (when authorized), configure retention, delete expired (per policy)

> Local-only tenants: backups must remain locally available without cloud connectivity.

---

## Security and Access Control

### Platform roles
Super Administrator, Platform Administrator, Infrastructure Administrator, Support Engineer, Billing Administrator, Read-Only Auditor

### Security features
RBAC, MFA, session management, login history, failed login monitoring, IP allowlisting, audit logs, secret rotation, secure credential storage, tenant isolation, access expiration, support access approval

### Audited events
Tenant creation/suspension/deletion, DB/storage/hosting config changes, credential rotation, module activation, subscription changes, backup/restore, user permission changes, deployment operations

> Support engineers must NOT have unrestricted access to tenant business data.

---

## Admin Panel Pages

Dashboard, Tenant Management, Tenant Details, Tenant Creation Wizard, Hosting Configuration, Database Configuration, Storage Configuration, Infrastructure Management, Deployment Management, Provisioning Jobs, ERP Module Catalog, Subscription Management, Billing and Invoices, Backup Management, Monitoring and Health, System Logs, Audit Logs, Platform Users, Roles and Permissions, Integration Management, System Settings, Platform Documentation

### Tenant Details tabs
Overview, Business Information, Hosting, Database, Storage, Modules, Subscription, Usage, Backups, Monitoring, Logs, Security, Deployment History

---

## Dashboard KPIs
Total/active/suspended/provisioning tenants, failed deployments, total active users, total storage/DB usage, subscription revenue, upcoming renewals, failed backup jobs, infrastructure health

### Charts
Tenant growth, subscription distribution, hosting distribution, DB provider distribution, storage provider distribution

### Filters
Date range, hosting mode, tenant status, subscription plan

---

## Backend Services Architecture

```
TenantService, HostingService, DatabaseProviderService, StorageProviderService,
ProvisioningService, SubscriptionService, ModuleManagementService,
BackupService, MonitoringService, AuditService, AuthenticationService, AuthorizationService
```

### Provider interface pattern
```typescript
interface DatabaseProvider {
  validate(config: DatabaseConfig): Promise<ValidationResult>;
  testConnection(config: DatabaseConfig): Promise<ConnectionResult>;
  provision(config: DatabaseConfig): Promise<ProvisioningResult>;
  migrate(config: DatabaseConfig): Promise<MigrationResult>;
  healthCheck(config: DatabaseConfig): Promise<HealthResult>;
  backup(config: DatabaseConfig): Promise<BackupResult>;
  restore(config: DatabaseConfig, backupId: string): Promise<RestoreResult>;
}
```

> Implement concrete adapters per provider. Do NOT fake provider behavior.

---

## Control-Plane DB Schema (key entities)

`PlatformUser, Role, Permission, Tenant, TenantUser, TenantConfiguration, HostingConfiguration, DatabaseConfiguration, StorageConfiguration, InfrastructureResource, Subscription, SubscriptionPlan, Module, TenantModule, ProvisioningJob, Deployment, Backup, BackupPolicy, UsageMetric, HealthCheck, AuditLog, Integration, SecretReference`

> Use JSON fields ONLY for genuinely provider-specific config that cannot be normalized. Do NOT store all config in one unstructured JSON field.

---

## Tenant Deployment Agent

For LAN and local-only tenants, a lightweight agent installed on the tenant's server handles:
- Health reporting
- Deployment updates
- Backup execution
- Database migration
- Resource monitoring
- Configuration synchronization

For fully offline environments: supports signed update packages and local administration without central platform connectivity.

---

## Recommended DB per Hosting Mode

| Deployment | Database | Storage |
|---|---|---|
| Fully hosted SaaS | PostgreSQL | S3-compatible |
| VPS | PostgreSQL or MySQL | Local disk or MinIO |
| LAN | PostgreSQL | Local server storage |
| Single-machine local | SQLite | Local filesystem |
| Neon-hosted | Neon PostgreSQL | S3-compatible |
| Firebase-based | Firestore | Firebase Storage |

---

## Definition of Done

Complete when:
- Admin can create a tenant and configure hosting/database/storage
- System validates configuration
- Provisioning workflow runs end-to-end
- Tenant receives ERP modules
- Admin can monitor tenant health
- Admin can manage subscriptions
- Admin can create and restore backups
- RBAC enforced
- Audit logs maintained
- All important actions work end-to-end
- Deployable from documentation

> Prioritize functional, secure, extensible system over visually impressive but nonfunctional prototype.
