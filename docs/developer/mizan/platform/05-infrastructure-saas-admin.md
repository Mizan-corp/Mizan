# Mizan — Infrastructure, SaaS Admin Panel & Hosting
Source: ChatGPT Main chat, messages [2–31], Nov 2026
GPT models: gpt-6, gpt-6-mini

---

## Multi-Tenant SaaS Admin Panel Requirements

### What it must do
The admin panel (Admoon) lets you create, configure, deploy, monitor, and manage ERP tenants independently.

Each tenant must have its own **hosting configuration**. One tenant could use fully-hosted SaaS, another could run on a local machine.

### Hosting modes supported
| Mode | Description |
|---|---|
| Fully hosted SaaS | Tenant runs on your shared cloud infrastructure |
| Local only (1 machine) | Tenant runs on their own machine, never internet-accessible |
| LAN | Tenant runs on local network, accessible within office/building |
| VPS | Tenant rents a virtual private server |
| Dedicated server | Tenant has own physical machine |
| Hybrid | Different components on different hosting modes |

### Database options per tenant
| Option | Notes |
|---|---|
| PostgreSQL (Neon) | ✓ Current production choice — pooled URL, RLS isolation |
| PostgreSQL (self-hosted) | VPS or local option |
| MySQL | Legacy option |
| Firebase | Not recommended for ERP (ACID transaction limitations) |
| In-app database (SQLite) | Local-only mode only — not suitable for SaaS |

**Decision: PostgreSQL with RLS is the right choice for multi-tenant ERP.** Firebase's transaction model is too limited for ERP business invariants.

---

## Infrastructure Recommendations

### Recommended server for production SaaS
From GPT analysis (message [5]):
- **Linux-based**: Ubuntu or Debian
- **Containerized**: Docker + Docker Compose for isolation
- **Database**: PostgreSQL (separate from app containers)
- **Control plane**: Separate from tenant workloads
- **Reverse proxy**: Nginx or Traefik (handles SSL, routing to containers)

### Important architecture principle
- **Control plane server** (manages tenants, subscriptions, deployments): separate from **tenant workload servers**
- Offer dedicated database/infrastructure option for enterprise tenants
- Design for portability from day one — never hardcode infrastructure assumptions

---

## Local Server Strategy (for bootstrapping without VPS budget)

### When to use your own server
From messages [6–9]:
- Development and testing: YES
- LAN deployments for local businesses: YES
- Validating the business without monthly VPS costs: YES
- Global SaaS-grade uptime promise: NO

> "Use your own server to build the product and validate the business without monthly VPS costs. Don't promise global SaaS-grade uptime from a single local machine. Design for portability now, and move the customer-facing production workload when you have the budget or revenue."

### Making a local server reachable
1. Assign a static local IP
2. Port forward 80/443 on router
3. Use a domain with dynamic DNS (Cloudflare Tunnel is better — no open ports)
4. Get a free SSL certificate (Let's Encrypt)

### Risks of local-only hosting
- Internet outage = all tenants offline
- Power failure = data at risk without UPS
- Home/office bandwidth is asymmetric (uploads slow)
- No geographic redundancy
- No guaranteed uptime SLA

---

## Hardware Sizing Guide

### Starting setup (development + first tenants)
From message [15]:
- **CPU**: Core i5 8th–10th Gen
- **RAM**: 32 GB
- **Storage**: 1 TB NVMe
- **Capacity**: ~10–30 small businesses (10–30 users each, normal workload)

### Capacity estimation (per tenant, normal workload)
| Workload type | Description |
|---|---|
| Light | Basic accounting, sales, inventory |
| Normal | Full ERP operations and reports |
| Heavy | Manufacturing, warehouses, analytics |

**Concurrent user estimation (20–30% of registered users are active simultaneously)**

For 30 companies × 30 users = 900 registered → ~180–270 concurrent

### 100-company target
From messages [18–25]:
- 100 companies × 30 users = **3,000 registered users**
- Expected concurrent: ~300–500 active at any time
- Target hardware: **not a single workstation** — needs cluster architecture or high-spec server

**15,000 EGP budget shopping list** (message [25]):
- HP Z440 Tower Workstation or HP P520
- Xeon E5 v4 6-core
- 32 GB ECC RAM (upgrade path: 256 GB max)
- 512 GB NVMe + 2 TB HDD for backups
- Gigabit network card
- UPS required in datacenter

> Treat this as your first development/pilot node, then expand with additional servers.

**HP Z440 evaluation** (message [27]):
- CPU: Intel Xeon E5-1600/2600 v4 (up to 22 cores)
- RAM: up to 256 GB ECC
- PCIe: 4 slots (add NVMe cards, network cards)
- Good for: development server, first 5–20 tenant pilot
- Not enough for: 1,500 actively working ERP users

---

## Cluster Architecture

### What a cluster is (message [29])
Multiple physical servers working together as one platform. Distributes workload; gives more capacity and fault tolerance.

**Two goals of a cluster:**
1. **Scaling**: more servers so the platform handles more users
2. **High availability**: if one server fails, the ERP keeps running

### How it's managed (message [31])
- **Kubernetes**: industry standard for container orchestration
- **Rancher**: dashboard to manage Kubernetes infrastructure (simpler UI)
- **Docker Swarm**: simpler alternative to Kubernetes for smaller deployments

**Important distinction:**
> "You write the ERP; Kubernetes manages where and how its components run. Rancher gives you a dashboard to manage infrastructure. Admoon is your ERP's own admin panel for managing companies, users, subscriptions, and modules. These are two separate management systems."

### Kubernetes components
- **Master node**: runs control plane (API server, scheduler, etcd)
- **Worker nodes**: run your ERP containers
- **kubectl**: CLI to manage the cluster
- **Helm**: package manager for Kubernetes apps
- **Persistent volumes**: database storage that survives container restarts

---

## Admoon Control Plane (Mizan's own admin panel)

### What it does
- Tenant wizard: create and configure new tenants
- Database and hosting metrics per tenant
- Plan subscriptions and MRR tracking
- Provisioning jobs
- License issuance and revocation (all four deployment modes)
- Audit logs
- Tenant impersonation (SaaS: direct; BYOD: via API key; LAN/Desktop: not supported)
- Cross-mode visibility: health, metrics, license status for SaaS, BYOD, LAN, and Desktop tenants

### Access
- Route: `/admoon`
- Admin credentials on a fresh database: `ammar` / `changeme` (created by `python manage.py db migrate`; change immediately)
- Requires `is_super_admin` flag on user

### Key endpoints
- `GET /admoon/overview` — platform-level stats
- `GET /admoon/tenants` — list all tenants with sales volume
- `POST /admoon/tenants` — provision new tenant
- `POST /admoon/tenants/{id}/impersonate` — login as tenant admin

---

## Deployment Modes

Mizan supports four deployment modes. Tenants choose at onboarding; migration between modes must be possible without data loss.

| Mode | Database | Network | Use case |
|---|---|---|---|
| **Standalone Desktop** | Embedded SQLite / PostgreSQL | None | Single operator, kiosk, fully offline |
| **LAN Server** | PostgreSQL on tenant's server | Local network only | Multi-user, single location |
| **BYOD** | Tenant-owned (Neon/Supabase/VPS/Firebase) | Internet for frontend | Technical tenants wanting data sovereignty |
| **Fully Managed SaaS** | Neon (Mizan-operated) | Internet | Zero-ops tenants |

All four modes issue a license key from Admoon. LAN and Desktop modes operate offline with a 14-day heartbeat grace period.

### Tenant Deployment Agent (LAN + BYOD)
Required for Admoon visibility on non-SaaS modes. Runs on tenant server. Outbound-only HTTPS to Admoon. Handles: health reporting, update packages, backup execution, migration runs, log shipping, license heartbeat.

---

## SaaS Lifecycle (current production — Fully Managed mode)

### Signup flow
`/signup` (account draft → sessionStorage)
→ `/onboarding` (step 1: sector → step 2: company + scale → step 3: palette + features)
→ `POST /platform/signup`
→ tenant created (14-day trial) + owner created + `demo_seed` workspace (sector-tailored)
→ fetch `/auth/me` before `setUser` (signup response lacks permissions)
→ auto-login → trial banner → `/pricing`
→ `POST /platform/subscribe-request` (manual activation until payment provider wired)

### Plans
| Plan | Price | Arabic name |
|---|---|---|
| Starter | 499 ج.م/month | أساسي |
| Pro | 999 ج.م/month | احترافي |
| Enterprise | Custom | مؤسسي |

### Feature toggles
Set in onboarding wizard (step 3):
- Credit sales / quotations
- Purchases
- HR module
- Any vertical module

Stored per tenant as feature flags. Gate navigation based on active flags.

### Payment providers (NOT YET IMPLEMENTED)
- **Fawry** — Egyptian payment gateway
- **Paymob** — Egyptian payment gateway
- **InstaPay** — Egyptian instant payment
- Manual activation currently — this is the highest-priority business gap

---

## Official Website & Marketing Site

### Design prompt (message [33])
Multi-section SaaS marketing website + product documentation portal. Inspired by Landingfolio SaaS gallery for polished layouts, strong product presentation, and conversion-focused design.

### Sections
1. Hero (dominant headline + product visual + primary CTA)
2. Social proof / trust strip
3. Feature showcase with interactive demo panels
4. Industries served (module grid — 30 industry types)
5. Pricing
6. Documentation portal
7. Blog / content hub
8. Contact / demo request
9. Footer

### Technology recommendation for marketing site
- React + Vite (matches ERP frontend)
- GSAP + Motion + Lenis for motion
- Optionally: Three.js for 3D hero elements
- Rive for interactive illustrations

### Important implementation rule
> Always implement Arabic text in actual HTML/CSS with real Arabic fonts. Never use AI-generated images for Arabic text — the letter shaping is incorrect. Use image generation for composition, colors, and atmosphere only.
