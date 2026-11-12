# Mizan — Platform Requirements (Source Notes)
Source: ChatGPT Main chat, message [11], Nov 2026 (gpt-6)
These source notes are expanded by the formal SRS at `../srs/SRS-Mizan-v1.0.md`.

---

## Architecture Principle

Build the ERP as a **portable application**, not one permanently tied to a local server. This allows cheap development now with a clean path to datacenter when revenue supports it.

Requirements are split into MVP (build now) and Later (design for now, build later).

---

## 1. SaaS Platform System Requirements

### Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| SYS-001 | Create, suspend, activate, archive, and delete tenant accounts through controlled workflows | MVP |
| SYS-002 | Maintain tenant profile, business activity, region, deployment mode, plan, and status | MVP |
| SYS-003 | Enforce tenant isolation for every request, query, file, and background job | **Critical MVP** |
| SYS-004 | Support tenant-specific users, roles, permissions, and organization structure | **Critical MVP** |
| SYS-005 | Provision tenant configuration and initial data automatically | MVP |
| SYS-006 | Select default modules from business activity and scale; modules self-configure for that activity | MVP |
| SYS-007 | Track subscription status, plan limits, usage, and billing events | MVP |
| SYS-008 | Support tenant login branding, system-wide appearance, layout, locale, timezone, and currency | MVP |
| SYS-009 | Provide audit logs for security-sensitive and business-critical actions | **Critical MVP** |
| SYS-010 | Support tenant export, backup, restore, and controlled offboarding | MVP |
| SYS-011 | Provide platform-wide monitoring, logs, alerts, and error tracking | MVP |
| SYS-012 | Support migration between Desktop, LAN Server, BYOD, and Fully Managed SaaS without data loss | Later — design for it now |
| SYS-013 | Support dedicated database or infrastructure isolation for selected tenants | Later |
| SYS-014 | Provide controlled platform upgrades and rollback | MVP |
| SYS-015 | Issue signed licenses for tenants in every deployment mode | MVP |
| SYS-016 | Let the admin panel technically manage and support tenants in every deployment mode | MVP |
| SYS-017 | Show activity-specific screenshot previews in module selection | MVP |

> **Critical:** Tenant isolation must be enforced in the application AND data-access layer, not just by hiding tenants in UI. Authentication alone does NOT guarantee isolation.

### Non-Functional Requirements

| Area | Requirement |
|---|---|
| Security | TLS for remote access; strong password hashing; MFA for platform admins |
| Authorization | RBAC, least privilege, tenant-scoped permissions |
| Data protection | Encrypted backups; defined retention; tested restore process |
| Availability | Documented uptime target; alerting for outages and resource exhaustion |
| Performance | Response-time targets; measure p95 latency under representative load |
| Scalability | Add application instances without changing tenant business logic |
| Maintainability | Modular monolith initially; stable domain boundaries and DB migrations |
| Observability | Centralized logs, metrics, health checks, request IDs, tenant-aware diagnostics |
| Recovery | Documented RPO/RTO targets and disaster-recovery procedures |
| Privacy | Tenant data export, retention rules, deletion workflow, restricted support access |

---

## 2. Tenant Deployment Requirements

### Deployment Modes

| Mode | Requirement |
|---|---|
| Standalone desktop | One executable with an embedded app-level database; no network service required |
| LAN server | Full system hosted on the tenant's server for local-network access |
| Bring-your-own database | Frontend hosted anywhere; database on the tenant's VPS, Firebase, Neon, or Supabase |
| Fully managed SaaS | Platform hosts and operates the application and database |

Every mode supports license issuance. The admin panel supports technical management and support across all modes.

### Deployment Profiles

| Profile | Minimum Hardware | Database |
|---|---|---|
| Standalone desktop | 4 CPU cores, 8 GB RAM, SSD | Embedded app-level SQLite or equivalent |
| Small LAN business | 4 CPU cores, 16 GB RAM, SSD | PostgreSQL |
| Medium LAN business | 8 CPU cores, 32 GB RAM, NVMe | PostgreSQL |
| BYOD | Depends on tenant workload | Tenant-owned VPS, Firebase, Neon, or Supabase |
| Central SaaS | Start measured; separate app and DB as load grows | PostgreSQL |

> These are initial estimates, not guaranteed limits. User concurrency, reports, inventory volume, background jobs, and file uploads can change sizing substantially.

### Installer/Admin Panel Must Collect Per Deployment
- Deployment mode and tenant identifier
- Database provider, connection details, credentials
- Storage provider and storage path
- Public domain or LAN address
- HTTPS configuration (for remote deployments)
- Backup destination and retention policy
- Timezone, locale, and currency
- Enabled modules and tenant limits
- Update channel and current application version
- License status and renewal/heartbeat state

> Do NOT store raw database passwords in ordinary tenant settings. Keep secrets in environment config or dedicated secrets store.

---

## 3. Tenant Isolation and Database Models

| Model | Description | Use |
|---|---|---|
| Shared database | Tenant-owned records share tables, partitioned by tenant ID | Cost-efficient starting model |
| Separate schema | Each tenant has own schema in one database | Stronger separation for selected customers |
| Separate database | Each tenant has independent database | Higher isolation, independent backup/restore |
| Dedicated deployment | Tenant receives separate app + database infrastructure | Enterprise or special requirements |

**Recommendation:** Start with PostgreSQL + shared database + tenant ID on all records. Design the data-access layer to allow migration of selected tenants to separate schemas or databases later. Make the model configurable per tenant.

---

## 4. Security Requirements — Do NOT Postpone

Implement BEFORE any real customer data is stored:

- [ ] Every request must resolve a valid tenant context
- [ ] Every tenant-owned DB operation must enforce tenant scope
- [ ] Background jobs must carry tenant identity and authorization context
- [ ] File storage paths must be tenant-scoped and access-controlled
- [ ] Platform admins must NOT automatically have unrestricted access to customer business data
- [ ] Support access must be authorized, logged, and time-limited
- [ ] Tenant deletion must handle: databases, files, exports, backup retention
- [ ] Automated tests must attempt cross-tenant access and verify denial

> **Tenant isolation is expensive to retrofit. Build it as an explicit architecture requirement from the beginning.**

---

## 5. Local Server Requirements (First Pilot)

Minimum stack for your own server:
- Ubuntu Server LTS
- Docker Compose
- PostgreSQL
- ERP application container
- Reverse proxy (Caddy recommended)
- Redis + worker container
- Persistent volumes for DB and files
- Automated database backups
- Off-server backup destination
- Monitoring for: disk, memory, CPU, service health, backup failures

> Before treating as customer-facing production: define your recovery procedure from server failure and how customers will be notified during outages.

---

## 6. Implementation Order

Realistic build order:

1. Tenant identity and tenant isolation
2. Authentication, roles, and permissions
3. Tenant creation and provisioning
4. Module and subscription entitlements
5. Tenant configuration and deployment profiles
6. Database and file-storage adapters
7. Backups, restore, and tenant export
8. Monitoring, audit logs, and alerts
9. Upgrade and migration workflows
10. Dedicated tenant deployments and advanced scaling

---

## 7. Server Hardware Reference

### Development / First Pilot (own server)
- **Model**: Dell OptiPlex 7070/7080 Tower, Lenovo ThinkCentre M920t, or HP EliteDesk 800 G5
- CPU: Intel Core i5-9500 or i7-9700
- RAM: 32 GB DDR4 (upgrade path to 64 GB)
- Storage: 1 TB NVMe (add 2 TB HDD for backups)
- UPS: 1000–1500 VA line-interactive
- Capacity: ~10–30 small businesses (10–30 users each, normal workload)

### Best budget option in Egypt (~15,000 EGP)
- **Lenovo ThinkStation P520**: Xeon W-2145 (8 cores/16 threads), 48 GB ECC RAM, 512 GB NVMe — ~13,500 EGP
- ECC memory + 8 DIMM slots + up to 256 GB RAM expansion
- Treat as first development/pilot node, not final production

### HP Z440 evaluation
- Xeon E5 v3/v4 (up to 8 cores), 128 GB ECC RAM max, PCIe expansion
- Good for development server and 5–20 tenant pilot
- NOT sufficient for 1,500 actively working ERP users

### 100 companies / 1,500 concurrent users (target)
- Requires multi-server cluster architecture
- Application server: AMD Ryzen 9 7900/7950X, 64 GB RAM, 2 TB NVMe
- Database server: AMD Ryzen 9 7900, 128 GB RAM, 2×2 TB enterprise NVMe
- Budget: ~150,000 EGP for pilot two-server setup

### Cluster management tools
- **K3s** (lightweight Kubernetes) — control plane + worker nodes
- **kubectl** — CLI for deploying, inspecting, scaling, troubleshooting
- **Rancher** — web dashboard for managing multiple Kubernetes clusters
- **Argo CD** — deployment automation (keeps apps synced with Git)
- **Docker** — container runtime
- **PostgreSQL primary + replica** — database layer
- **Redis** — shared cache, sessions, job queue
- **Shared file storage** — all app servers access the same files

> "You write the ERP; Kubernetes manages where and how its components run. Rancher gives you a dashboard to manage infrastructure. The admin panel is your ERP's own admin panel — these are two separate management systems."

---

## 8. SaaS Platform Architecture (Production)

```
ERP Users + Platform Admins
           |
    DNS / CDN / WAF
           |
    Reverse Proxy / Load Balancer
           |
    ┌──────────────┐
    │ App Server 1 │──── Redis ──── Background Workers
    │ App Server 2 │       │
    └──────────────┘       │
           |               │
    PostgreSQL Primary ────┘
    PostgreSQL Replica
           |
    Off-site Backups
    Shared File Storage
    SaaS Control Plane (separate)
```

### Deployment recommendation summary
| Stage | Setup | Purpose |
|---|---|---|
| Development | PC + Docker | Building and testing |
| Pilot | Dedicated local server on LAN | First tenants + internal testing |
| Remote access | Local server + secure tunnel (Cloudflare Tunnel) | Access from outside network |
| Growth | Local server + secondary server or later VPS | More tenants, better uptime |
| Production | Datacenter or cloud + cluster | When revenue supports |

---

## 9. Business-Activity-Aware Modularization

- Business activity and scale determine default modules and integrations.
- Modules apply activity-specific defaults automatically; common modules such as POS need no manual setup.
- Module selection shows screenshot previews for the selected activity.
- Each business page maps to one discrete module with clear service-style boundaries.
- Tenants can customize the login screen, branding, layout, and system-wide appearance.
