# Mizan Knowledge Base — Index
14 documents across 5 categories.

---

## frontend/
Design, UI, UX, motion, brand — everything the user sees.

| File | Contents |
|---|---|
| `02-brand-design-system.md` | Color tokens, typography, Tailwind patterns, composition language ("daily ledger"), component rules |
| `04-ux-quality-gates.md` | 10 UX dimensions AI misses, full UI/UX checklist, Mizan-specific patterns (POS, dashboard, nav) |
| `06-purpose-built-activity-ui.md` | Purpose-built UI profiles for 14 activity types — modules self-configure from the selected activity |
| `08-brand-identity-full.md` | Full brand spec: hex palette (Oxblood Burgundy `#651E2C`, Warm Ivory `#F5EBDD`), all 4 fonts, logo directions, Arabic copy |
| `09-motion-engineering-prompt.md` | Full $9,000-quality motion prompt — per-page spec for all 10 routes, timing tokens, RTL motion rules |
| `10-marketing-website-master-prompt.md` | Full master prompt for marketing site + docs portal — IA, all pages, components, motion brief |

---

## backend/
API, database, tenancy, security, testing.

| File | Contents |
|---|---|
| `03-engineering-quality-gates.md` | 16 engineering dimensions AI misses, tenancy rules, transaction integrity, migrations, security, performance, full checklist + agent prompt |

---

## platform/
SaaS infrastructure, admin panel, hosting, deployment — all four modes.

| File | Contents |
|---|---|
| `05-infrastructure-saas-admin.md` | Four deployment modes (Desktop/LAN/BYOD/SaaS), hardware guide, cluster architecture, Admoon, licensing, SaaS lifecycle |
| `07-saas-admin-panel-master-prompt.md` | Full Admoon master prompt — 21 sections including all four deployment modes, license management, cross-mode visibility |
| `11-system-requirements-srs.md` | Platform source notes — deployment modes, licensing, tenant isolation, hardware, cluster stack |

---

## srs/
Formal, consolidated system requirements.

| File | Contents |
|---|---|
| `SRS-Mizan-v1.0.md` | Full SRS — activity-aware modules, tenant customization, four deployment modes, licensing, Admoon support, acceptance criteria |

---

## engineering/
Architecture, standards, requirements, learning roadmap.

| File | Contents |
|---|---|
| `01-erp-requirements-30-types.md` | Complete ERP requirements for all 30 business types — every ID (CORE, FIN, CRM, PUR, INV, HR, SYS) + 30 industry-specific modules |
| `12-software-engineering-standards.md` | Architecture standards (ISO, DDD, C4, SOLID), distributed systems, security (OWASP ASVS, STRIDE), SRE, 6-phase learning roadmap, essential books |

---

## Quick Reference

**Stack:** FastAPI + SQLAlchemy + PostgreSQL (Neon) / React 19 + Vite + Tailwind v4 + shadcn/ui v4

**Deploy:** Backend → Vercel Git (master) · Frontend → Vercel CLI only · DB → Neon

**Non-negotiables:**
1. Three-layer tenancy: ORM filter + before_flush + PostgreSQL RLS
2. Every mutation in one atomic transaction
3. `.num` class on every financial figure
4. `PageHeader` on every screen
5. Arabic copy throughout
6. Frontend deploy is CLI-only — NOT git-linked

**Open priorities:**
- ⚠️ Fawry/Paymob payment wiring (blocking monetization)
- ⚠️ ETA e-Invoicing module
- ⚠️ Split fat routers (hr.py 1024 lines, admoon.py 1183 lines)
