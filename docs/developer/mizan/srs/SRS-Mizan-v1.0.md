# Software Requirements Specification
## ميزان (Mizan) — Modular Multi-Tenant ERP SaaS Platform
**Version:** 1.1  
**Date:** 2026-11-07  
**Status:** Draft  
**Prepared by:** Kiro (based on ChatGPT design sessions)

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
2b. [Modularization and Deployment Architecture](#2b-modularization-and-deployment-architecture)
3. [System Actors and User Classes](#3-system-actors-and-user-classes)
4. [Functional Requirements — Shared Core](#4-functional-requirements--shared-core)
5. [Functional Requirements — Industry Modules](#5-functional-requirements--industry-modules)
6. [Functional Requirements — SaaS Platform](#6-functional-requirements--saas-platform)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [External Interface Requirements](#8-external-interface-requirements)
9. [Data Requirements](#9-data-requirements)
10. [Security Requirements](#10-security-requirements)
11. [Deployment Requirements](#11-deployment-requirements)
12. [Constraints and Assumptions](#12-constraints-and-assumptions)
13. [Acceptance Criteria Summary](#13-acceptance-criteria-summary)

---

## 1. Introduction

### 1.1 Purpose
This SRS defines the complete functional, non-functional, interface, data, security, and deployment requirements for **ميزان (Mizan)** — a modular, multi-tenant SaaS ERP platform built for Arabic-speaking markets, initially targeting Egyptian building-materials merchants.

### 1.2 Scope
Mizan is a single platform that serves up to 30 business types through a shared core and activatable industry-specific modules. Each business (tenant) operates in complete data isolation. The platform supports four deployment modes: Standalone Desktop, LAN Server, Bring-Your-Own-Database, and Fully Managed SaaS. All modes are supported by a central license system and managed through Admoon.

### 1.3 Definitions

| Term | Definition |
|---|---|
| Tenant | One business organization; owns all its data |
| Module | A feature set activatable per tenant (e.g., POS, HR, Manufacturing) |
| Business Activity | The industry type selected during onboarding (e.g., retail, restaurant, pharmacy). Drives the default module set, UI layout, and integrations |
| Activity Profile | A pre-configured bundle of modules, settings, and UI behaviors mapped to a Business Activity |
| Self-configuration | A module's ability to adapt its UI, defaults, and feature flags automatically based on the active Business Activity without manual setup |
| Admoon | The super-admin control plane for managing all tenants across all deployment modes |
| TenantScoped | Any database table that carries `tenant_id` and is isolated by RLS |
| RLS | PostgreSQL Row-Level Security — enforces tenant isolation at DB level |
| ORM filter | SQLAlchemy global query filter that injects `tenant_id == ctx` |
| Migration | A tracked, idempotent SQL change in `shared/backend/app/db/migrations.py` |
| `.num` | CSS class applied to every financial figure for tabular lining display |
| Shift | A cashier work session with opening/closing balance |
| Demo data | Seeded data with `is_demo = true` — can be wiped via `/platform/wipe-demo` |
| Standalone Desktop | Deployment mode: single executable with embedded database, runs on a single device, no network required |
| LAN Server | Deployment mode: full system on tenant's own server, accessible over local network |
| BYOD (Bring Your Own Database) | Deployment mode: frontend hosted anywhere; tenant-owned database (VPS/Neon/Supabase/Firebase) |
| Fully Managed SaaS | Deployment mode: all infrastructure operated by Mizan platform |
| License Key | A cryptographically signed token that activates Mizan for a specific deployment mode and tenant |

### 1.4 References
- SYSTEM.md — `/home/ammar/projects/Mizan/SYSTEM.md`
- AGENTS.md — `/home/ammar/projects/Mizan/AGENTS.md`
- TASKS.md — `/home/ammar/projects/Mizan/TASKS.md`
- DESIGN_SYSTEM.md — `/home/ammar/projects/Mizan/frontend/DESIGN_SYSTEM.md`
- Knowledge base — `/home/ammar/.kiro/crew/workspace/knowledge/mizan/`

### 1.5 Overview
This document is organized as: system description → actors → shared core requirements (FIN, CRM, INV, HR, SYS) → industry module requirements → SaaS platform requirements → non-functional requirements → interfaces → data → security → deployment → constraints.

---

## 2. Overall Description

### 2.1 Product Perspective
Mizan replaces disconnected business tools (spreadsheets, paper ledgers, standalone POS) with one unified system. It is a web-first, Arabic RTL, PWA-capable application.

### 2.2 Product Functions (high level)
- Point of Sale with offline support
- Sales, invoicing, quotations, returns
- Inventory (multi-warehouse, O(1) reads)
- Purchasing and supplier management
- Customers and supplier ledgers
- Finance (safes, wallets, accounting periods)
- HR and payroll (biometric attendance)
- SaaS onboarding, trial management, subscription
- Tenant-branded storefronts
- Platform administration (Admoon)
- Background automation (shift close, ZK sync, WhatsApp)

### 2.3 User Characteristics

| User | Technical level | Primary surface |
|---|---|---|
| Cashier | Low — daily POS use | POS terminal |
| Branch manager | Medium — reports, shifts | Dashboard, reports |
| Accountant | Medium — invoices, periods | Finance, sales, purchasing |
| HR manager | Medium — payroll, attendance | HR module |
| Business owner | Low — overview | Dashboard, Admoon (own tenant) |
| Platform super-admin | High | Admoon control plane |
| Developer | High | API, migrations |

### 2.4 Operating Environment
- Browser: Chrome 120+, Firefox 120+, Safari 17+
- Mobile: iOS 16+, Android 12+
- Backend: Vercel (serverless), Neon PostgreSQL (pooled)
- Frontend: Vercel CDN
- Offline: IndexedDB for POS queue

### 2.5 Design and Implementation Constraints
- All user-facing copy in Arabic
- All financial figures with `.num` class and `ar-EG-u-nu-latn` locale
- All money stored as `Numeric/Decimal`, never float
- All timestamps stored in UTC
- Frontend deploy is CLI-only (not git-linked)
- Backend deploy is git-only (push to master)
- `CORS_ORIGINS` is a Vercel env var, not in code

### 2.6 Assumptions and Dependencies
- Neon PostgreSQL supports RLS with FORCE policy
- PgBouncer transaction mode requires GUC re-application per transaction
- Vercel serverless functions support async PostgreSQL connections via asyncpg
- ZKTeco biometric devices are reachable on port 4370 on the local network

---

## 2b. Modularization and Deployment Architecture

### 2b.1 Business-Activity-Aware Modules

Mizan's modularization is inspired by Odoo but goes further: each module **self-configures based on the active Business Activity** so the result feels purpose-built rather than general-purpose.

**Principles:**
- A business selects its Business Activity during onboarding. This selection drives the default module set, UI layout, field labels, default workflows, and demo data — automatically, with no manual setup required.
- Each module exposes an **Activity Profile** — a set of configuration defaults that are applied when a given Business Activity is active. For example, the POS module shows a floor-plan view for restaurants, a product-grid view for retail, and a prescription queue for pharmacies — all from the same module.
- Common modules (POS, Finance, HR, Inventory) must self-customize per Business Activity without requiring the tenant admin to manually configure each screen.
- A single business page maps cleanly to one discrete module. Modules have microservice-style boundaries: no module reaches into another module's data layer directly.
- Every module in the marketplace/selection UI must show screenshot previews of how it looks for the selected Business Activity.
- Business Activity determines the lean vs full stack default: a small retail shop gets POS + Inventory + Sales; a manufacturing company gets the full stack including BOM, MRP, and Payroll.

**Activity-to-module mapping examples:**

| Business Activity | Default modules | POS self-configuration |
|---|---|---|
| Retail / بقالة | POS, Inventory, Sales, Purchasing, Finance | Product grid, barcode, receipt |
| Restaurant / مطعم | POS, Menu, KDS, Table Management, Finance | Floor plan, kitchen display, modifiers |
| Pharmacy / صيدلية | POS, Drug Master, Prescriptions, Inventory | Prescription queue, expiry alerts, FEFO |
| Gym / جيم | Membership, Scheduling, POS, HR | Membership card scan, class booking |
| Clinic / عيادة | Appointments, EMR, Billing, Pharmacy | Patient lookup, encounter form |
| Wholesale / جملة | Sales, Purchasing, Inventory, Finance | Order book, quantity tiers |
| Manufacturing / تصنيع | BOM, MRP, Production, Inventory, HR | Work order board, kanban |

### 2b.2 Tenant Customization

Tenants must be able to fully customize their experience:

| Customization area | What the tenant controls |
|---|---|
| Login screen | Logo, background image, brand colors, welcome message |
| Branding | Brand hue (`--brand-hue`), logo, store name, favicon, PWA icons |
| Layout | Sidebar collapsed/expanded default; preferred density (compact vs comfortable) |
| System-wide appearance | Light/dark mode default; color theme preset |
| Navigation | Show/hide modules; reorder nav groups |
| Module configuration | Per-module settings (e.g., POS layout, KDS station names) |

### 2b.3 Deployment Modes

Mizan supports four deployment modes. A tenant chooses one at onboarding. Migration between modes must be possible without data loss.

#### Mode 1 — Standalone Desktop
- Exported as a single executable (Electron or Tauri app)
- Embedded database: SQLite or embedded PostgreSQL
- No network service required; runs on one device
- Fully offline; license validated locally via signed license key
- Backup: local file export; manual off-device copy
- Suitable for: single-operator shops, kiosks, offline-first deployments
- Limitations: single user; no multi-branch; no cloud sync

#### Mode 2 — LAN Server
- Full system hosted on the tenant's own server (Linux/Windows)
- Database: PostgreSQL on the same server
- Accessible by multiple devices over local network
- Internet not required for daily operation; optional for updates and remote access
- License: validated against server MAC/UUID with periodic heartbeat
- Backup: local automated backups + optional off-site (SFTP/NAS)
- Suitable for: multi-user, single-location businesses

#### Mode 3 — Bring Your Own Database (BYOD)
- Frontend hosted by tenant (Vercel, Netlify, VPS, or Mizan CDN)
- Database on tenant's own infrastructure: VPS PostgreSQL, Neon, Supabase, or Firebase
- Mizan provides: backend application container + connection configuration wizard
- Tenant controls: database credentials, storage bucket, backup schedule
- License: validated per database endpoint fingerprint
- Suitable for: technical tenants who want data sovereignty

#### Mode 4 — Fully Managed SaaS (current production)
- Everything hosted and operated by Mizan
- Multi-tenant PostgreSQL with RLS on Neon
- License: subscription plan enforced by platform
- Suitable for: all tenants who want zero-ops

### 2b.4 Licensing

All four deployment modes use a unified license system:

| Requirement | Detail |
|---|---|
| License format | Cryptographically signed JWT: tenant ID, mode, plan, expiry, feature flags |
| Standalone Desktop | License embedded in app bundle; validated offline; re-validates against Admoon on internet availability |
| LAN Server | License validated against server hardware fingerprint; heartbeat to Admoon every 7 days; 14-day offline grace period |
| BYOD | License validated against database endpoint fingerprint; periodic online check |
| Fully Managed SaaS | License enforced server-side by Admoon; no client-side validation needed |
| License issuance | Admoon control plane issues all license keys |
| License revocation | Admoon can revoke; LAN/Desktop honor revocation on next heartbeat |
| Trial | 14-day trial for all modes; full feature access during trial |

### 2b.5 Admoon Across Deployment Modes

Admoon must support technical management and support for tenants across all four modes:

| Capability | SaaS | BYOD | LAN | Desktop |
|---|---|---|---|---|
| View tenant health | Direct | Via agent | Via agent | Via agent (on heartbeat) |
| View tenant metrics | Direct | Via agent | Via agent | Last heartbeat snapshot |
| Push updates | Vercel deploy | Container pull | Agent-pushed package | Signed update bundle |
| Run migrations | Direct | Agent-executed | Agent-executed | Bundle includes migrations |
| Revoke license | Immediate | On next check | On next heartbeat | On next heartbeat |
| Impersonate admin | Direct | Via API key | Via VPN/tunnel | Not supported |
| View logs | Direct | Log shipping | Log shipping | On heartbeat upload |

**Tenant Deployment Agent** (required for LAN and BYOD modes):
- Lightweight process installed on tenant's server
- Handles: health reporting, update application, backup execution, migration runs, metric collection, log shipping, license heartbeat
- Communicates with Admoon over HTTPS (outbound-only from tenant server)
- Supports offline operation with queued sync on reconnect
- Signed update packages for fully offline environments

---

## 3. System Actors and User Classes

### 3.1 Primary Actors

**Cashier (كاشير)**
- Opens/closes shift
- Processes sales, returns, payments
- Scans barcodes; uses F2/F3/Esc shortcuts
- Works offline when network unavailable

**Branch Manager (مدير الفرع)**
- Views shift reports and Z-reports
- Manages stock transfers and adjustments
- Approves returns and cancellations

**Accountant (محاسب)**
- Manages invoices, expenses, wallets, safes
- Closes accounting periods
- Generates financial reports

**HR Manager (مدير الموارد البشرية)**
- Manages employees and attendance
- Runs payroll: draft → review → approve → pay

**Tenant Owner / Admin (صاحب العمل)**
- Manages users, roles, permissions
- Configures store settings, brand hue, modules
- Subscribes to plans; views MRR

**Platform Super-Admin (Admoon)**
- Provisions tenants
- Monitors all tenants
- Impersonates tenant admins for support
- Views platform-wide MRR and metrics

**API Consumer (Developer)**
- Integrates with REST API
- Uses JWT Bearer or cookie auth
- Accesses OpenAPI docs at `/api/docs`

---

## 4. Functional Requirements — Shared Core

### 4.1 Core Platform (CORE)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| CORE-01 | Multi-company (tenant) management | Must | Each tenant has isolated data; one user cannot access another tenant's data in any scenario |
| CORE-02 | Multi-branch and multi-warehouse | Must | Each warehouse has independent stock; transfers create stock movements |
| CORE-03 | Role-Based Access Control | Must | Permission gate `require_perm` on every sensitive endpoint; UI hides inaccessible nav items |
| CORE-04 | User management with granular permissions | Must | Owner can create users, assign roles, reset passwords |
| CORE-05 | Configurable approval workflows | Should | Configurable per tenant via settings |
| CORE-06 | Audit trail for critical actions | Must | AuditLog entry written for every destructive or financial mutation |
| CORE-07 | Notifications center | Must | In-app bell, unread badge, read/unread state; WhatsApp dispatch queued to background worker |
| CORE-08 | Document attachments | Should | File upload with tenant-scoped S3-compatible storage |
| CORE-09 | Custom fields | Could | Configurable via tenant settings |
| CORE-10 | Dashboard and configurable reporting | Must | Dashboard shows daily sales masthead figure, sparkline, ruled sections |
| CORE-11 | Search, filtering, sorting, pagination | Must | Every list endpoint paginated; Ctrl+K global search palette |
| CORE-12 | Import/export (CSV, Excel, PDF) | Should | Excel export on sales; PDF for invoices and payslips |
| CORE-13 | Localization: Arabic RTL, timezone, currency | Must | `dir="rtl"` on document; `ar-EG-u-nu-latn` locale; UTC storage |
| CORE-14 | Configurable numbering sequences | Must | Invoice numbers, PO numbers, receipt numbers configurable per tenant |
| CORE-15 | Data archival and retention | Should | Soft-delete with `is_archived`; never hard-delete financial records |

### 4.2 Finance and Accounting (FIN)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FIN-01 | General Ledger | Must | Double-entry; every transaction produces balanced journal entries |
| FIN-02 | Chart of Accounts | Must | Configurable per tenant; seeded with defaults at signup |
| FIN-03 | Accounts Receivable | Must | Customer balance updated on every sale, return, payment |
| FIN-04 | Accounts Payable | Must | Supplier balance updated on every PO, receipt, payment |
| FIN-05 | Journal Entries | Must | Manual journal entry with debit/credit validation |
| FIN-06 | Customer and supplier invoices | Must | Invoice → confirm → payment in one atomic transaction |
| FIN-07 | Credit notes and debit notes | Must | Return/cancellation produces credit note; stock restored atomically |
| FIN-08 | Cash and bank management (safes + wallets) | Must | Multiple safes and wallets per tenant; transactions tracked |
| FIN-09 | Bank reconciliation | Should | Manual reconciliation workflow |
| FIN-10 | Tax configuration and reporting | Must | VAT configurable per tenant; invoice tax lines |
| FIN-11 | Cost centers and profit centers | Should | Optional tagging on transactions |
| FIN-12 | Balance Sheet, P&L, Cash Flow | Must | Reports available under `/reports` |
| FIN-13 | Fiscal periods and period closing | Must | Monthly accounting periods; close workflow; re-open by super-admin only |
| FIN-14 | Budget vs actual | Should | Budget entry per period per category |
| FIN-15 | Multi-currency | Should | Exchange rate configurable; base currency per tenant |

### 4.3 Sales and CRM (CRM)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| CRM-01 | Customer database with profiles | Must | Customer name, phone, address, credit limit, balance |
| CRM-02 | Customer contacts and history | Should | Communication log per customer |
| CRM-03 | Quotations and sales orders | Must | Quotation → invoice conversion; status tracked |
| CRM-04 | Pricing rules and price lists | Must | Retail/wholesale price tiers per product |
| CRM-05 | Discounts and promotions | Must | Per-item discount on invoice; configurable promotion rules |
| CRM-06 | Customer credit limits | Must | System prevents sale above credit limit (configurable override) |
| CRM-07 | Sales returns and refunds | Must | Partial/full return; stock restored; credit note issued |
| CRM-08 | Customer segmentation | Should | Customer type (retail/wholesale/credit) |

### 4.4 Procurement and Supplier Management (PUR)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| PUR-01 | Supplier database | Must | Name, phone, address, balance, credit terms |
| PUR-02 | Purchase requisitions | Should | Internal request before PO |
| PUR-03 | Purchase orders | Must | PO creation → receive → invoice matching |
| PUR-04 | Goods Receipt Notes | Must | Receiving increases stock; partial receiving supported |
| PUR-05 | Supplier invoice matching | Must | 3-way match: PO / receipt / invoice |
| PUR-06 | Supplier payments | Must | Payment reduces supplier balance |
| PUR-07 | Supplier performance | Should | On-time delivery rate, price variance |
| PUR-08 | Purchase price history | Must | Per product per supplier; used for cost reporting |

### 4.5 Inventory and Warehouse (INV)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| INV-01 | Product and item master | Must | Name, barcode(s), category, subcategory, unit, prices |
| INV-02 | Stock on hand (O(1) reads) | Must | `stock_balances` maintained table; atomic update on every movement |
| INV-03 | Stock movements | Must | Every stock change produces a `stock_movements` record |
| INV-04 | Inventory valuation (Weighted Average) | Must | Cost updated on every purchase receipt |
| INV-05 | Reorder points and low-stock alerts | Must | Alert notification when stock falls below reorder point |
| INV-06 | Cycle counting and adjustments | Must | Stocktake creates adjustment movement and AuditLog entry |
| INV-07 | Barcode scanning | Must | Global barcode listener (`useBarcodeScanner`); 80mm + 58mm ESC/POS thermal printing |
| INV-08 | Multiple warehouses | Must | Stock tracked per warehouse; transfers between warehouses |
| INV-09 | Per-warehouse stock valuation | Must | `/stock/valuation` returns totals object per warehouse |
| INV-10 | Product images and categories | Must | Image upload; category/subcategory hierarchy per tenant |

### 4.6 HR and Payroll (HR)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| HR-01 | Employee profiles | Must | Name, job title, department, salary, contract type |
| HR-02 | Department structure | Must | Departments and org chart per tenant |
| HR-03 | Attendance (manual + biometric) | Must | Manual entry; CSV import; ZKTeco device sync (port 4370) |
| HR-04 | Leave and absence | Must | Leave types configurable; deducted from payroll |
| HR-05 | Payroll processing | Must | Draft → review → approve → pay; one period at a time |
| HR-06 | Salary components | Must | Base, allowances, deductions, advances configurable |
| HR-07 | Employee expenses | Should | Expense claims with approval |
| HR-08 | Performance evaluations | Could | Rating per period |
| HR-09 | Onboarding/offboarding | Should | Status transitions and checklists |
| HR-10 | Shift scheduling | Must | Shift assignment per employee; links to POS shift |
| HR-11 | Payslips | Must | PDF payslip per employee per period via print token |
| HR-12 | Egypt-specific payroll | Must | Social insurance, income tax, configurable per employee |

### 4.7 Common Technical Requirements (SYS)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| SYS-01 | REST API with OpenAPI docs | Must | All endpoints documented at `/api/docs` |
| SYS-02 | Webhooks / event-driven | Should | Webhook dispatch for key tenant events |
| SYS-03 | Transaction integrity | Must | Every business mutation in one atomic DB transaction |
| SYS-04 | Backup and disaster recovery | Must | Neon automated backups; tested restore procedure |
| SYS-05 | Encryption in transit | Must | TLS only; no plaintext traffic |
| SYS-06 | Authentication | Must | JWT httpOnly cookie + Bearer fallback; CSRF double-submit |
| SYS-07 | Performance monitoring | Must | `/health` returns `{"status":"ok","database":"connected"}`; Sentry error tracking |
| SYS-08 | Automated testing | Must | 107 e2e tests in CI; 9 vitest unit tests; `tsc --noEmit`; build |
| SYS-09 | Configurable business rules | Should | Module feature flags per tenant stored in DB |
| SYS-10 | Data migration | Must | All migrations in `shared/backend/app/db/migrations.py`; idempotent; tracked by version |

---

## 5. Functional Requirements — Industry Modules

Each module below is activatable per tenant via feature flags. All inherit the shared core (Section 4).

### 5.1 Point of Sale — POS (✅ Shipped)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| POS-01 | POS terminal with barcode scanner | Must | Global barcode listener; scan adds item to cart |
| POS-02 | Real-time stock synchronization | Must | Stock deducted atomically on sale confirm |
| POS-03 | Retail and wholesale price tiers | Must | Price tier auto-applied based on customer type |
| POS-04 | Credit sales with limit enforcement | Must | Blocked if customer over credit limit (configurable override) |
| POS-05 | Split payments | Must | Multiple payment methods per invoice |
| POS-06 | Hold and resume sale | Must | Draft sale persisted; cashier can switch |
| POS-07 | Offline sale queue | Must | IndexedDB queue; auto-replay on reconnect; conflict logged |
| POS-08 | F2/F3/Esc keyboard shortcuts | Must | Configurable velocity shortcuts |
| POS-09 | Shift enforcement | Must | Cashier must open shift before selling; shift badge in topbar |
| POS-10 | Thermal receipt printing | Must | 80mm and 58mm ESC/POS; Egyptian Tax/ZATCA QR format |
| POS-11 | Cash drawer reconciliation | Must | Opening float → sales → closing float → Z-report |
| POS-12 | Offline stock collision policy | Must | Insufficient stock → negative balance + `AuditLog(inventory_discrepancy)` |

### 5.2 Sales Module (✅ Shipped)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| SAL-01 | Invoice creation and management | Must | Draft → confirm → pay in one atomic transaction |
| SAL-02 | Quotation to invoice conversion | Must | Quotation status tracked; converts without re-entering data |
| SAL-03 | Partial and full returns | Must | Return restores stock; issues credit note |
| SAL-04 | Invoice cancellation | Must | Cancellation restores stock and customer balance |
| SAL-05 | Excel export of sales | Must | Export with all line items and payments |
| SAL-06 | Scoped print documents | Must | 60s `scope=print` token; browser-opened PDF |
| SAL-07 | Invoice status pipeline | Must | Draft → Confirmed → Paid / Partial / Cancelled |

### 5.3 Inventory Module (✅ Shipped)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| INV-M-01 | Per-warehouse stock balances | Must | O(1) read from `stock_balances`; updated atomically |
| INV-M-02 | Stock transfers between warehouses | Must | Transfer creates two movements (out + in) |
| INV-M-03 | Stocktaking (physical count) | Must | Count entry → variance calculation → adjustment |
| INV-M-04 | Low-stock alerts | Must | Alert notification on reorder-point breach |
| INV-M-05 | Per-warehouse valuation | Must | `/stock/valuation` returns totals per warehouse |
| INV-M-06 | Product barcodes (multiple per product) | Must | Each barcode maps to one product |

### 5.4 HR and Payroll Module (✅ Shipped)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| HR-M-01 | ZKTeco biometric device sync | Must | Network ping; punch-to-attendance harmonization |
| HR-M-02 | CSV offline attendance import | Must | Import CSV; reconcile against device records |
| HR-M-03 | Payroll draft → approve → pay flow | Must | One period active at a time; revert requires super-admin |
| HR-M-04 | Payslip PDF generation | Must | Via print token; one payslip per employee per period |
| HR-M-05 | Payroll advances | Must | Advance reduces net salary for the period |

### 5.5 Finance Module (✅ Shipped)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FIN-M-01 | Safe management (multiple safes) | Must | Deposit, withdrawal, transfer between safes |
| FIN-M-02 | Wallet management (multiple wallets) | Must | Each wallet has a balance; transfers tracked |
| FIN-M-03 | Expense management | Must | Expense with category, amount, attachment |
| FIN-M-04 | Cash flow report | Must | Inflow/outflow by period |
| FIN-M-05 | Aging report | Must | Customer/supplier overdue balances by age bucket |
| FIN-M-06 | Accounting period close | Must | Period lock; reopening requires super-admin |
| FIN-M-07 | Collection management | Must | Batch payment collection against outstanding invoices |

### 5.6 Storefront Module (✅ Shipped)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| STR-01 | Public product catalog | Must | Tenant-branded; no auth required |
| STR-02 | Shopping cart and checkout | Must | Order submitted to merchant dispatch board |
| STR-03 | Coupon engine | Must | Percentage and fixed-amount coupons |
| STR-04 | Merchant dispatch board | Must | Real-time web orders appear for merchant to process |
| STR-05 | Storefront theme from store settings | Must | Brand hue, logo, store name applied to storefront |

### 5.7 Restaurant Module (✅ Scaffolded)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| RES-01 | Menu and menu-item configuration | Must | Categories, items, modifiers (toppings, sizes, extras) |
| RES-02 | Recipe and ingredient-level BOM | Must | Ingredient consumption per item; stock deducted on sale |
| RES-03 | Kitchen Display System (KDS) | Must | Dark screen; large font; timer per ticket; station routing |
| RES-04 | Table management and floor plan | Must | Visual floor layout; color = status (free/occupied/bill-requested) |
| RES-05 | Order routing by kitchen station | Must | Item → station mapping in menu config |
| RES-06 | Split bills | Must | Split by item or by amount |
| RES-07 | Food waste and spoilage tracking | Should | Manual waste entry; deducts from stock |
| RES-08 | Delivery platform integration | Could | Webhook from delivery platforms |

### 5.8 Pharmacy Module (✅ Scaffolded)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| PHA-01 | Drug master with active ingredients | Must | Drug name, active ingredient, dosage form, unit |
| PHA-02 | Batch and expiration tracking | Must | FEFO picking; expiry warning per batch |
| PHA-03 | Prescription processing | Must | Prescription linked to sale; controlled drug flag |
| PHA-04 | Drug interaction checking | Should | Warning on dispensing interacting drugs together |
| PHA-05 | Recalled/quarantined medication | Must | Flag + block dispensing; AuditLog entry |
| PHA-06 | Insurance claim processing | Should | Claim submission and tracking |

### 5.9 Healthcare Clinic Module (✅ Scaffolded)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| HLT-01 | Patient registration and EMR | Must | Patient profile; visit history |
| HLT-02 | Appointment scheduling | Must | Physician calendar; time-slot booking |
| HLT-03 | Electronic prescriptions | Must | Linked to pharmacy module |
| HLT-04 | Patient billing | Must | Billing per encounter; insurance claim generation |

### 5.10 School Module (✅ Scaffolded)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| EDU-01 | Student admissions and enrollment | Must | Student profile; guardian contacts |
| EDU-02 | Class and timetable scheduling | Must | Room assignment; no scheduling conflicts |
| EDU-03 | Examination and grading | Must | Grade entry per student per subject per period |
| EDU-04 | Tuition fees and installment schedules | Must | Fee plan; payment collection |
| EDU-05 | Student transcripts | Should | PDF transcript via print token |

### 5.11 Gym Module (✅ Scaffolded)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| GYM-01 | Membership lifecycle | Must | Active/frozen/expired; renewal reminders |
| GYM-02 | Recurring billing | Must | Auto-invoice on renewal date |
| GYM-03 | Class and trainer scheduling | Must | Class capacity; booking per member |
| GYM-04 | Member check-in (one tap) | Must | Scan card or search → logged immediately |
| GYM-05 | Trainer commissions | Must | Per-session tally; included in payroll |

### 5.12 Hotel / Hospitality Module (✅ Scaffolded)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| HOT-01 | Room inventory and types | Must | Room grid with color = status |
| HOT-02 | Reservation and occupancy | Must | Check-in/out; guest folio |
| HOT-03 | Room rate management | Must | Rate per room type per season |
| HOT-04 | Housekeeping task management | Must | Room status updates by housekeeping staff |
| HOT-05 | Night audit | Must | One-button daily close; revenue reconciliation |
| HOT-06 | Hotel POS integration | Must | F&B charges posted to guest folio |

### 5.13 WhatsApp Gateway Module (✅ Scaffolded — dispatch pending)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| WA-01 | Settings schema | Must | Cloud API token, phone number ID, template selector, auto-send toggles |
| WA-02 | Receipt dispatch via worker | Must | Background job sends WhatsApp receipt after sale confirm |
| WA-03 | Message log | Must | Log entry per dispatch; status tracked |

### 5.14 ETA e-Invoicing Module (⚠️ Not built)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| ETA-01 | ETA portal submission queue | Must | Invoice → queue → submit to Egyptian Tax Authority |
| ETA-02 | Document signing | Must | UUID, issuer tax ID, activity code, 14% VAT + 1% WHT |
| ETA-03 | Submission status dashboard | Must | Accepted / Rejected / Pending per invoice |

### 5.15 Loyalty Rewards Module (⚠️ Not built)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| LOY-01 | Points per EGP spent | Must | Configurable rate per tenant |
| LOY-02 | Bronze / Silver / Gold tiers | Must | Auto-upgrade on cumulative spend thresholds |
| LOY-03 | In-POS points redemption | Must | Cashier applies points as payment method |
| LOY-04 | Points balance statements | Must | Customer-facing balance history |

### 5.16 Module Marketplace and Self-Configuration (⚠️ Not built)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| MOD-01 | Module marketplace UI | Must | Grid of available modules; each shows name, description, screenshot preview for the active Business Activity |
| MOD-02 | Activity-driven module defaults | Must | On Business Activity selection, system pre-activates the default module set for that activity without manual toggle |
| MOD-03 | Module self-configuration per activity | Must | Each module reads the active Business Activity and applies its Activity Profile automatically on first activation |
| MOD-04 | Screenshot previews in marketplace | Must | Each module shows at least one screenshot of how it looks for the current Business Activity before activation |
| MOD-05 | Business size-based stack | Must | Onboarding wizard detects small/medium/large scale and activates a lean or full module stack accordingly |
| MOD-06 | Single page per module boundary | Must | Every page in the UI is owned by exactly one module; no page spans two modules' data domains |
| MOD-07 | Module dependency declaration | Must | Each module declares its dependencies; system prevents activation when a dependency is missing |
| MOD-08 | Module deactivation | Must | Deactivating a module hides its navigation items and disables its API routes; data is preserved |

### 5.17 Tenant Customization (⚠️ Not built)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| CUS-01 | Custom login screen | Must | Tenant can upload logo, set background image, set welcome message; shown on `/login` |
| CUS-02 | Brand hue and logo | Must | Already exists; tenant sets `--brand-hue` and logo in store settings |
| CUS-03 | Light/dark mode default | Must | Tenant sets the default theme; users can override personally |
| CUS-04 | Sidebar layout preference | Should | Default collapsed/expanded; default density (compact vs comfortable) |
| CUS-05 | Navigation customization | Should | Tenant admin can hide modules and reorder nav groups |
| CUS-06 | PWA icons from logo | Must | Upload logo → system generates PWA icons automatically |

### 5.18 Banking / Financial Institution Module (⚠️ Not built)

This is a specialized financial system, not a standard business ERP. Operations must enforce tenant-scoped permissions, transaction integrity, and audit records.

| ID | Requirement | Priority |
|---|---|---|
| BNK-01 | Customer and account master management | Must |
| BNK-02 | Double-entry financial transaction engine | Must |
| BNK-03 | Account balances and transaction history | Must |
| BNK-04 | Payment processing and settlement | Must |
| BNK-05 | Reconciliation and settlement reporting | Must |
| BNK-06 | Loan origination and servicing | Must |
| BNK-07 | Interest and fee calculation | Must |
| BNK-08 | KYC (Know Your Customer) workflows | Must |
| BNK-09 | AML (Anti-Money Laundering) monitoring | Must |
| BNK-10 | Regulatory reporting | Must |
| BNK-11 | Risk management and exposure monitoring | Must |
| BNK-12 | Segregation of duties and transaction authorization | Must |
| BNK-13 | Financial audit and immutable transaction logs | Must |
| BNK-14 | Multi-entity consolidation | Must |

### 5.19 Insurance Module (⚠️ Not built)

| ID | Requirement | Priority |
|---|---|---|
| INS-01 | Insurance product and coverage configuration | Must |
| INS-02 | Policy lifecycle management | Must |
| INS-03 | Policy underwriting | Must |
| INS-04 | Premium calculation and rating | Must |
| INS-05 | Premium billing and collection | Must |
| INS-06 | Policy renewals and endorsements | Must |
| INS-07 | Claims registration and processing | Must |
| INS-08 | Claims assessment and approval | Must |
| INS-09 | Claims reserves and financial liabilities | Must |
| INS-10 | Reinsurance management | Must |
| INS-11 | Broker and agent commissions | Must |
| INS-12 | Fraud detection and risk scoring | Must |
| INS-13 | Insurance regulatory reporting | Must |
| INS-14 | Customer and policyholder portal | Must |

### 5.20 Government / Nonprofit Module (⚠️ Not built)

| ID | Requirement | Priority |
|---|---|---|
| GOV-01 | Fund accounting | Must |
| GOV-02 | Budget allocation and budget controls | Must |
| GOV-03 | Budget versus actual reporting | Must |
| GOV-04 | Grant and funding management | Must |
| GOV-05 | Multi-year budget planning | Must |
| GOV-06 | Procurement compliance and tendering | Must |
| GOV-07 | Public-sector project management | Must |
| GOV-08 | Beneficiary and citizen management | Must |
| GOV-09 | Public expenditure tracking | Must |
| GOV-10 | Government audit and accountability reporting | Must |
| GOV-11 | Restricted fund and donor reporting | Must |
| GOV-12 | Program and outcome performance measurement | Must |

### 5.21 Entertainment / Gaming Module (⚠️ Not built)

| ID | Requirement | Priority |
|---|---|---|
| ENT-01 | Event and experience catalog | Must |
| ENT-02 | Ticket and admission management | Must |
| ENT-03 | Ticket inventory and capacity control | Must |
| ENT-04 | Ticket scanning and access control | Must |
| ENT-05 | Membership and season pass management | Must |
| ENT-06 | Package and bundle management | Must |
| ENT-07 | Event scheduling and venue management | Must |
| ENT-08 | Dynamic ticket pricing | Must |
| ENT-09 | Ticket cancellation and refund management | Must |
| ENT-10 | Revenue sharing and event settlement | Must |
| ENT-11 | Gaming equipment and asset management | Must |
| ENT-12 | Player or visitor loyalty management | Must |

### 5.22 Oil / Gas Module (⚠️ Not built)

| ID | Requirement | Priority |
|---|---|---|
| OIL-01 | Field and site operations management | Must |
| OIL-02 | Well and asset hierarchy management | Must |
| OIL-03 | Production volume and operational reporting | Must |
| OIL-04 | Drilling and field activity tracking | Must |
| OIL-05 | Maintenance and reliability management | Must |
| OIL-06 | HSE and incident management | Must |
| OIL-07 | Permit-to-work and operational safety | Must |
| OIL-08 | Contractor and service company management | Must |
| OIL-09 | Equipment and spare parts tracking | Must |
| OIL-10 | Hydrocarbon inventory and custody transfer | Must |
| OIL-11 | Production cost allocation | Must |
| OIL-12 | Environmental and emissions reporting | Must |
| OIL-13 | Field procurement and logistics | Must |
| OIL-14 | Joint venture and partner cost allocation | Must |

For these modules, acceptance requires the stated workflow, tenant-scoped permissions, and auditable sensitive changes.

---

## 6. Functional Requirements — SaaS Platform

### 6.1 Tenant Lifecycle (PLAT)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| PLAT-01 | Self-serve signup (3-step onboarding) | Must | Sector → company+scale → palette+features → tenant created |
| PLAT-02 | Demo data seeding on signup | Must | Sector-tailored demo data with `is_demo=true` |
| PLAT-03 | 14-day free trial | Must | Trial banner shown; plan gating after expiry |
| PLAT-04 | Demo data self-service wipe | Must | `POST /platform/wipe-demo` deletes all `is_demo=true` rows |
| PLAT-05 | Subscription plans | Must | أساسي 499 ج.م / احترافي 999 ج.م / مؤسسي custom |
| PLAT-06 | Subscribe request | Must | `POST /platform/subscribe-request`; manual activation |
| PLAT-07 | Payment provider integration | ⚠️ Must | Fawry + Paymob + InstaPay — **not yet built** |
| PLAT-08 | Feature flags per tenant | Must | Module activation stored per tenant; gates navigation |
| PLAT-09 | Per-tenant brand hue | Must | Onboarding wizard writes `--brand-hue`; applied in CSS |
| PLAT-10 | Tenant deletion cascades | Must | Deleting tenant cascades to ALL business tables including users |

### 6.2 Admoon Control Plane (ADMN)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| ADMN-01 | Tenant overview dashboard | Must | Total tenants, MRR, active users, storage |
| ADMN-02 | Tenant list and management | Must | Create, suspend, reactivate, delete tenants |
| ADMN-03 | Tenant impersonation | Must | Login as tenant admin for support; logged in AuditLog |
| ADMN-04 | Plan subscription management | Must | Upgrade/downgrade/cancel plans |
| ADMN-05 | Database metrics | Must | Connection pool utilization, query stats |
| ADMN-06 | Provisioning jobs | Must | Background job status and history |
| ADMN-07 | Audit logs | Must | All platform-level actions with user, timestamp, before/after |
| ADMN-08 | Platform user RBAC | Must | Super Admin, Platform Admin, Support Engineer, Auditor roles |

### 6.2b Deployment Mode Management (DEPL)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| DEPL-01 | Tenant selects deployment mode during onboarding | Must | Mode selection in onboarding wizard step 1; mode stored per tenant |
| DEPL-02 | Standalone Desktop build | Must | CI produces a signed single-file executable (Electron or Tauri) with embedded DB |
| DEPL-03 | LAN Server installer package | Must | CI produces a self-contained installer (Docker Compose bundle or native package) |
| DEPL-04 | BYOD connection wizard | Must | UI wizard to configure external DB connection (PostgreSQL/Neon/Supabase/Firebase) and validate connection |
| DEPL-05 | Migration between deployment modes | Must | Export/import tool preserves all tenant data; documented migration path for each mode transition |
| DEPL-06 | Deployment Agent for LAN and BYOD | Must | Lightweight agent installed on tenant server; handles health, updates, backups, migrations, log shipping |
| DEPL-07 | Agent outbound-only HTTPS communication | Must | Agent connects to Admoon; Admoon never connects inbound to tenant network |
| DEPL-08 | Offline operation with queued sync | Must | LAN/Desktop modes work without internet; queue syncs to Admoon when connectivity restored |

### 6.2c License Management (LIC)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| LIC-01 | License issuance from Admoon | Must | Admoon issues signed license JWT for every tenant regardless of deployment mode |
| LIC-02 | License format | Must | Signed JWT: tenant ID, deployment mode, plan, expiry, feature flags |
| LIC-03 | Standalone Desktop license | Must | License embedded in app bundle; validates offline; re-validates on internet availability |
| LIC-04 | LAN Server license | Must | Validated against server hardware fingerprint; heartbeat every 7 days; 14-day offline grace |
| LIC-05 | BYOD license | Must | Validated against database endpoint fingerprint; periodic online check |
| LIC-06 | SaaS license | Must | Enforced server-side; no client-side validation |
| LIC-07 | License revocation | Must | Admoon can revoke any license; LAN/Desktop honor revocation on next heartbeat |
| LIC-08 | Trial for all modes | Must | 14-day full-feature trial for every deployment mode |
| LIC-09 | Admoon cross-mode visibility | Must | Admoon shows health, metrics, and status for all tenants across all four deployment modes |

### 6.3 Background Automation (AUTO)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| AUTO-01 | Midnight shift auto-close | Must | `python manage.py cron`; Z-report generated |
| AUTO-02 | Subscription enforcement | Must | Feature gating applied after trial expires |
| AUTO-03 | Daily metrics digest | Must | Platform metrics summary; delivered to super-admin |
| AUTO-04 | WhatsApp receipt dispatch | Must | Background worker processes queue; retryable |
| AUTO-05 | ZK attendance sync | Must | Device sync scheduled; punch-to-attendance harmonization |

### 6.4 Shared Cross-Industry Modules (XMOD)

Activate these reusable capabilities only for activities that need them. Each remains subject to tenant isolation, permissions, and audit rules.

| ID | Module | Required capabilities | Acceptance criteria |
|---|---|---|---|
| XMOD-01 | Workflow Engine | Configurable approval chains, conditions, and escalations | Admin can configure and test workflows; each decision is recorded |
| XMOD-02 | Notification Engine | Email, SMS, push notifications, and reminders | Messages can be scheduled, delivered, and tracked by status |
| XMOD-03 | Document Management | Attachments, versioning, permissions, and retention | Authorized users can add, retrieve, version, and expire documents |
| XMOD-04 | Reporting Engine | Custom reports, filters, and scheduled reports | Users can filter, export, and schedule permitted reports |
| XMOD-05 | Integration Engine | REST APIs, webhooks, and external connectors | Admin can configure connectors and inspect delivery or error status |
| XMOD-06 | Subscription Billing | Recurring invoices, plans, and renewals | Due charges and renewal status are recorded against the correct account |
| XMOD-07 | Scheduling Engine | Calendars, resources, availability, and conflict checks | Conflicting bookings are detected before confirmation |
| XMOD-08 | Pricing Engine | Price lists, discounts, tiers, and dynamic rules | The selected rule yields a reproducible transaction price |
| XMOD-09 | Inventory Engine | Stock ledger, transfers, reservations, and valuation | Stock changes are traceable and balances reconcile to movements |
| XMOD-10 | Quality Management | Inspections, nonconformance, and corrective actions | Findings link to inspections and track corrective status |
| XMOD-11 | Asset Management | Assets, maintenance, depreciation, and service history | Authorized users can review asset history and due maintenance |
| XMOD-12 | Project Management | Tasks, milestones, budgets, and resources | Project progress and budget use are visible to permitted users |
| XMOD-13 | Customer Portal | Customer accounts, documents, orders, and invoices | Customers can access only their permitted records |
| XMOD-14 | Supplier Portal | Purchase orders, invoices, and delivery schedules | Suppliers can access only records assigned to their account |
| XMOD-15 | Mobile Operations | Offline data capture, barcode scanning, and field workflows | Offline changes queue and sync without duplicate actions |

---

## 7. Non-Functional Requirements

### 7.1 Performance

| ID | Requirement | Target |
|---|---|---|
| PERF-01 | Stock balance read latency | p95 < 50ms (O(1) from `stock_balances`) |
| PERF-02 | Invoice creation latency | p95 < 500ms |
| PERF-03 | Dashboard page load | < 2s on 4G |
| PERF-04 | POS item scan response | < 200ms |
| PERF-05 | Report generation | < 10s for 1-year date range |

### 7.2 Reliability and Availability

| ID | Requirement | Target |
|---|---|---|
| REL-01 | API availability | 99.9% monthly uptime |
| REL-02 | POS offline capability | Sales must continue for up to 72h without network |
| REL-03 | Data durability | Zero data loss on confirmed transactions (Neon WAL) |
| REL-04 | Background job retry | All background jobs must be idempotent; retry up to 5 times |

### 7.3 Scalability

| ID | Requirement | Note |
|---|---|---|
| SCAL-01 | Stateless application layer | Multiple Vercel instances with shared Neon DB |
| SCAL-02 | Connection pooling | PgBouncer transaction mode; GUC re-applied per transaction |
| SCAL-03 | Module activation without downtime | Feature flag change takes effect on next request |

### 7.4 Maintainability

| ID | Requirement |
|---|---|
| MAINT-01 | All migrations tracked in `shared/backend/app/db/migrations.py`; idempotent |
| MAINT-02 | No business logic in routers; belongs in service layer |
| MAINT-03 | No new `components/ui.tsx` usages; migrate to `components/kit/` |
| MAINT-04 | All FK columns have indexes |
| MAINT-05 | `AGENTS.md` is the non-negotiable contract for all AI agents |

### 7.5 Usability

| ID | Requirement |
|---|---|
| USA-01 | All user-facing text in Arabic |
| USA-02 | `.num` class on every financial figure |
| USA-03 | `PageHeader` on every screen (no exceptions) |
| USA-04 | `ListState` (skeleton → error → empty → content) wrapping every data list |
| USA-05 | Minimum touch target 36px; floor 32px in dense tables |
| USA-06 | Destructive actions require confirmation dialog that explains what will be deleted |
| USA-07 | POS cashier must complete a sale in under 30 seconds |

### 7.6 Localization

| ID | Requirement |
|---|---|
| LOC-01 | Document `dir="rtl"`; logical CSS properties throughout |
| LOC-02 | `ar-EG-u-nu-latn` locale — Western digits, never Arabic-Indic |
| LOC-03 | All money stored as Numeric; displayed with `.num` class |
| LOC-04 | All timestamps stored UTC; displayed in tenant timezone |
| LOC-05 | IBM Plex Sans Arabic for all Arabic text |

### 7.7 System-Wide Non-Functional Requirements (NFR)

These apply across all business activities and deployment modes. Jurisdiction-specific and industry-specific rules must be defined before the affected module is released.

| ID | Requirement | Acceptance criteria |
|---|---|---|
| NFR-01 | Security: RBAC, least privilege, secure authentication, encryption | Role tests deny actions outside granted permissions; data is encrypted in transit and at rest |
| NFR-02 | Data isolation | Automated cross-tenant access tests deny access through APIs, databases, files, and jobs |
| NFR-03 | Auditability | Sensitive changes record actor, time, action, and before/after values |
| NFR-04 | Reliability | Financial and inventory operations commit atomically or leave no partial state |
| NFR-05 | Scalability | Load tests measure growth across users, branches, transactions, and data volume |
| NFR-06 | Performance | Response-time and transaction-throughput targets are defined and tested |
| NFR-07 | Availability | Uptime targets, maintenance windows, and recovery objectives are documented and monitored |
| NFR-08 | Disaster recovery | Backups are automated; restore procedures are tested and results recorded |
| NFR-09 | Data integrity | Constraints, validation, idempotency, and concurrency controls prevent invalid or duplicate records |
| NFR-10 | Maintainability | Modules have documented boundaries, APIs, migrations, and automated tests |
| NFR-11 | Localization | Currency, language, date format, and tax rules can be configured per tenant and region |
| NFR-12 | Observability | Structured logs, metrics, traces, and actionable alerts are available |
| NFR-13 | Accessibility | Core workflows support keyboard use, accessible forms, and readable interfaces |
| NFR-14 | Data portability | Tenant data can be exported and migrated in documented formats |
| NFR-15 | Compliance | Applicable industry and jurisdiction rules are recorded before release |

---

## 8. External Interface Requirements

### 8.1 User Interface

- **Web app:** Single Page Application at `mizan-co.vercel.app`
- **Framework:** React 19 + Vite + Tailwind v4 + shadcn/ui v4
- **Direction:** RTL; `dir="rtl"` on document
- **Typography:** IBM Plex Sans Arabic (Arabic), Manrope (English/UI)
- **Color:** Warm Editorial Luxury palette — Oxblood Burgundy, Deep Merlot, Warm Ivory, and Charcoal; tenant branding may override the base hue
- **PWA:** App-shell service worker; network-first navigations; never caches `/api/`
- **Offline:** IndexedDB sale queue (`lib/offline.ts`)

### 8.2 API Interface

- **Base URL:** `https://mizan-co-api.vercel.app/api`
- **Protocol:** HTTPS only; REST JSON
- **Auth:** JWT in httpOnly cookie; `X-CSRF-Token` header required (except `/auth/login`, `/platform/signup`, `/health`)
- **Bearer fallback:** `Authorization: Bearer <token>` for programmatic access
- **Print tokens:** `POST /auth/print-token` → 60s `scope=print` JWT; used as `?token=` query param
- **Docs:** OpenAPI at `/api/docs`

### 8.3 Hardware Interfaces

- **Barcode scanners:** USB HID keyboard-emulation; handled by `useBarcodeScanner` hook
- **Thermal printers:** 80mm and 58mm ESC/POS; Egyptian Tax/ZATCA QR
- **ZKTeco biometric:** TCP port 4370; network-accessible device

### 8.4 Software Interfaces

| System | Interface | Notes |
|---|---|---|
| Neon PostgreSQL | asyncpg + PgBouncer | Pooled URL in Vercel env |
| Vercel | Git push to master (backend) / CLI deploy (frontend) | Frontend is CLI-only |
| WhatsApp Cloud API | Meta Cloud API (v17+) | Background worker dispatch |
| ZKTeco SDK | TCP/IP on port 4370 | `zk_attendance` module |
| ETA (Egyptian Tax Authority) | REST API (TBD) | `eta_einvoice` module — not built |
| Fawry | REST API (TBD) | Payment — not built |
| Paymob | REST API (TBD) | Payment — not built |

---

## 9. Data Requirements

### 9.1 Tenancy Model

Every business row has `tenant_id UUID NOT NULL` with cascade delete. Three enforcement layers:

1. **ORM query filter** — `with_loader_criteria` injects `tenant_id == ctx` on all SELECT/UPDATE/DELETE
2. **before_flush stamp** — new `TenantScoped` rows get `tenant_id` from ContextVar
3. **PostgreSQL RLS** — `ENABLE FORCE` with policy: `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid`

GUC `app.tenant_id` is re-applied on every transaction via `after_begin` listener (PgBouncer safety).

RLS only binds roles without BYPASSRLS, so while a workspace is bound every transaction runs as `mizan_app` (`SET LOCAL ROLE`, migration v48b); the login role is used only with no workspace bound (scripts, migrations) (#112).

### 9.2 Data Model Summary

52 tables. 50 tenant-scoped, 2 platform-only.

**Platform-only:** `tenants`, `subscriptions`

**Tenant-scoped (key tables):**

| Domain | Tables |
|---|---|
| Products | products, categories, subcategories, barcodes, images |
| Stock | stock_balances, stock_movements, warehouses |
| Sales | sales, sale_items, sale_payments, customers, customer_payments |
| Purchasing | purchases, purchase_items, purchase_price_history |
| Finance | wallets, safes, safe_deposits, expenses, financial_categories, accounting_periods |
| HR | employees, hr_attendance, hr_shifts, hr_settings, hr_sync_log, hr_audit_log, hr_advance |
| Payroll | hr_payroll_periods, hr_payroll_entries, payroll_legacy |
| Platform | store_settings, notifications, device_tokens, audit_log, archive |
| Collections | collections, parties, supplier_transactions |

### 9.3 Migrations

- 35 tracked migrations (v0–v32) in `shared/backend/app/db/migrations.py`
- All new migrations must be appended to `MIGRATIONS` list
- Idempotent SQL: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`
- Migrations run with `app.bypass = 'on'`
- `create_all` at boot for new tables only; migrations own all column/constraint changes

### 9.4 Data Integrity Rules

- All money columns: `Numeric` type; never `Float`
- All timestamps: `DateTime` with timezone; stored UTC
- Composite per-tenant uniques replace global uniques
- `is_demo BOOLEAN NOT NULL DEFAULT FALSE` on all business tables
- Financial records: soft-delete only; never `DELETE`
- Posted accounting entries: immutable; correction via counter-entry only

---

## 10. Security Requirements

### 10.1 Authentication

| ID | Requirement |
|---|---|
| SEC-01 | JWT in httpOnly cookie; Secure flag; SameSite=Lax |
| SEC-02 | CSRF double-submit: cookie `csrf_token` echoed as `X-CSRF-Token` header |
| SEC-03 | Exempt from CSRF: `/auth/login`, `/platform/signup`, `/health` |
| SEC-04 | Login route shows app only when BOTH `token AND user` exist |
| SEC-05 | After signup: fetch `/auth/me` before `setUser` (signup response lacks `permissions`) |
| SEC-06 | Print tokens: 60s, `scope=print`, accepted as `?token=` only |
| SEC-07 | Rate limiting on auth endpoints |
| SEC-08 | Password hashing: bcrypt with configurable cost |

### 10.2 Authorization

| ID | Requirement |
|---|---|
| SEC-10 | `require_perm` dependency on every sensitive endpoint |
| SEC-11 | Role map in `app/core/roles.py`; configurable per tenant |
| SEC-12 | UI hides navigation items user cannot access |
| SEC-13 | Permission denied state is designed (not 404 or crash) |

### 10.3 Tenant Isolation

| ID | Requirement |
|---|---|
| SEC-20 | All three isolation layers always active (ORM + flush + RLS) |
| SEC-21 | No bypass path in application code |
| SEC-22 | Background jobs carry tenant identity and authorization context |
| SEC-23 | File storage paths are tenant-scoped and access-controlled |
| SEC-24 | Automated tests must attempt cross-tenant access and verify denial |
| SEC-25 | Admoon impersonation is logged in AuditLog; time-limited |

### 10.4 Audit Trail

| ID | Requirement |
|---|---|
| SEC-30 | `AuditLog` entry for every destructive or financial mutation |
| SEC-31 | Audit log includes: user, tenant, action, timestamp, old value |
| SEC-32 | Audit log is append-only; no delete endpoint |

### 10.5 Infrastructure Security

| ID | Requirement |
|---|---|
| SEC-40 | TLS everywhere; no plaintext traffic |
| SEC-41 | Secrets in Vercel environment variables; never in code |
| SEC-42 | `CORS_ORIGINS` JSON array in Vercel env (overrides `config.py`) |
| SEC-43 | Database credentials never exposed in logs, URLs, or frontend responses |

---

## 11. Deployment Requirements

### 11.1 Deployment Modes Overview

| Mode | Database | Network | Use case |
|---|---|---|---|
| Standalone Desktop | Embedded SQLite / PostgreSQL | None required | Single operator, kiosk, fully offline |
| LAN Server | PostgreSQL on tenant's server | Local network only | Multi-user, single location |
| BYOD | Tenant-owned (Neon/Supabase/VPS/Firebase) | Internet for frontend | Technical tenants wanting data sovereignty |
| Fully Managed SaaS | Neon (Mizan-operated) | Internet | Zero-ops tenants |

### 11.2 Fully Managed SaaS (current production)

| Component | Method | Notes |
|---|---|---|
| Backend | Vercel Git integration (master branch) | Root directory: `backend/`; rewrites `/api/* → /*` |
| Frontend | `npx vercel --prod --yes --token <TOKEN>` | CLI-only; NOT git-linked |
| Database | Neon managed PostgreSQL | Pooled URL; branch `br-still-sunset-aegj3ngq` |
| Migrations | `python3 manage.py db migrate` | Must run before any backend code change reaches production |

### 11.3 LAN Server Deployment

- Distributed as a Docker Compose bundle or native installer package
- Includes: application container, PostgreSQL, Redis, background worker, reverse proxy (Caddy/Nginx)
- Deployment Agent installed alongside; connects outbound to Admoon
- License validated against server hardware fingerprint; 14-day offline grace period
- Backups: local automated + optional SFTP/NAS off-site

### 11.4 Standalone Desktop Deployment

- Built as a signed Electron or Tauri executable
- Embedded database: SQLite (small volumes) or embedded PostgreSQL
- No network dependency for daily operation
- License embedded in bundle; re-validates when internet available
- Single-user; no multi-branch; no concurrent users
- Distribution: direct download from Admoon or signed package store

### 11.5 BYOD Deployment

- Tenant provides: database connection string (PostgreSQL/Neon/Supabase/Firebase)
- Mizan provides: backend application Docker image + connection wizard
- Deployment Agent optional but recommended for Admoon visibility
- License validated against database endpoint fingerprint
- Frontend: hosted by tenant or on Mizan CDN pointing to tenant database

### 11.6 Local Development

```bash
docker compose up -d                          # postgres :5433 + backend :8000
python3 manage.py db migrate                  # run tracked migrations
cd backend && .venv/bin/uvicorn main:app --port 8010
cd frontend && npm install && npm run dev     # :5173, /api proxied
```

### 11.7 Verification Requirements

Before any SaaS deployment:
```bash
cd frontend
npm test                    # 9 vitest unit tests — must pass
npx tsc -b --noEmit         # TypeScript check — must pass
npm run build               # build — must pass
```

For changes touching auth, sales, stock, or payroll:
```bash
cd e2e
E2E_API_BASE=… E2E_DATABASE_URL=… .venv/bin/pytest -q   # 107 tests — must pass
```

---

## 12. Constraints and Assumptions

### 12.1 Constraints

- Frontend deploy is intentionally CLI-only (Vercel project `mizan-app` not git-linked)
- Backend deploy is intentionally git-only (Vercel project `mizan-api`)
- `CORS_ORIGINS` must be updated in Vercel env when adding new frontend origins
- Migrations must be idempotent; no breaking migrations without coordinated deploy
- `/shifts/current` returns 200 + null when no shift is open (not 404)
- `/stock/valuation` returns a totals object, not rows
- Standalone Desktop mode is single-user only; no concurrent users
- LAN Server license requires periodic internet heartbeat (14-day grace); fully airgapped deployments must request an extended offline license from Admoon
- BYOD mode with Firebase requires a separate NoSQL-aware backend adapter (Firebase is not a relational DB equivalent)

### 12.2 Assumptions

- Users have modern browsers with JavaScript enabled
- Barcode scanners operate in USB HID keyboard-emulation mode
- ZKTeco devices are network-accessible on port 4370 within the LAN
- Neon PgBouncer is in transaction pooling mode
- ETA e-Invoicing API will be available via REST once integrated
- Fawry/Paymob/InstaPay will be integrated for subscription billing

---

## 13. Acceptance Criteria Summary

A feature is complete when ALL of the following pass:

### Backend
- [ ] Every new table has `ENABLE FORCE` RLS with `tenant_isolation` policy
- [ ] Every mutation is wrapped in a single DB transaction
- [ ] Every list endpoint is paginated (`page`, `size`, `total`, `pages`)
- [ ] No business logic lives in a router (belongs in a service)
- [ ] Migration appended to `shared/backend/app/db/migrations.py`, idempotent, numbered `v<N>_<name>`
- [ ] `AuditLog` entry exists for every destructive or financial mutation
- [ ] FK indexes exist on every FK column
- [ ] Money stored as `Numeric`, never `float`
- [ ] `is_demo = False` on all new seeded data

### Frontend
- [ ] All colors from `styles.css` tokens — nothing hardcoded
- [ ] All icons Lucide; sizes 16/18/20; never emoji
- [ ] `.num` class on every financial figure
- [ ] `PageHeader` present on every screen
- [ ] `ListState` wraps every data list
- [ ] One dominant action per state
- [ ] Destructive actions have a confirm dialog explaining what will happen
- [ ] All user-facing text in Arabic
- [ ] All interactive elements ≥ 36px touch target
- [ ] `dir="rtl"` on document; logical CSS properties throughout

### Testing
- [ ] `npm test` passes (9 unit tests)
- [ ] `npx tsc -b --noEmit` passes
- [ ] `npm run build` passes
- [ ] 107 e2e tests pass (if touching auth, sales, stock, or payroll)
- [ ] Each specialized module implements its listed BNK, INS, GOV, ENT, or OIL requirements
- [ ] Cross-industry modules meet their XMOD acceptance criteria
- [ ] Evidence exists for all NFR-01 through NFR-15

### Review question
> "Can a real employee complete the actual task quickly, confidently, and without making a costly mistake?"

---

## Modularization and Deployment Acceptance Criteria

### Module self-configuration
- [ ] Activating a module on a tenant with Business Activity = "restaurant" shows the restaurant-specific layout without any manual configuration
- [ ] Module marketplace shows screenshot previews relevant to the active Business Activity
- [ ] Onboarding wizard selects the appropriate lean/full module stack based on business size
- [ ] Each page is owned by exactly one module; no cross-module data access at the page level

### Tenant customization
- [ ] Custom login screen shows tenant logo and welcome message
- [ ] Brand hue, logo, and store name are applied site-wide including the login screen
- [ ] Tenant admin can hide any module from navigation without affecting data

### Deployment modes
- [ ] Standalone Desktop executable runs without any network connection
- [ ] LAN Server installer produces a working multi-user system accessible from other devices on the LAN
- [ ] BYOD connection wizard validates a Neon, Supabase, or PostgreSQL connection before proceeding
- [ ] All four modes can run the same ERP feature set (within plan limits)

### Licensing
- [ ] Admoon issues a valid license for every new tenant regardless of deployment mode
- [ ] LAN/Desktop mode operates normally for 14 days without internet; shows warning at day 10
- [ ] Revoking a license in Admoon prevents the tenant from logging in within one heartbeat cycle
- [ ] Trial period works identically across all four deployment modes
