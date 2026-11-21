# ميزان (Mizan) — Roadmap & Delivery Status

Current as of 2026-11-13. **Open work is tracked in [GitHub issues](https://github.com/mizan-corp/Mizan/issues)**; this file is the high-level summary of what has shipped.

## 0. Priority plan (updated 2026-11-13)

Done: ADR-006 phases 1–5 (module platform, permissions and acting roles, activities and variants
with pharmacy end to end, role screens and the screen builder); production safety (#114 files in
Vercel Blob, #64 releases migrate production from CI, #115 PWA paths, #63 deploy budget); the
cross-cutting fixes (#26, #27, #28, #59, #60, #61); on-site updates, backups and device binding
(#89, #90, #92). Open work in priority order; each step ships, is tested and deployed before the next.

**P0 — Production safety**
1. #85 Manual security follow-ups that need the owner (rotate the Paymob key, revoke old tokens).

**P1 — Getting paid and owner basics**
2. #65 Paymob live (Paymob activating the live account, expected 2026-11-15): test payments
   work end to end on production (callbacks repointed 2026-11-13); then swap in the live
   integrations. Done 2026-11-13: #68 plan changes (upgrades credit unused time as days,
   downgrades start at period end), and checked in production and closed: #69 receipts, #70,
   #74, #76, #79. Waiting on an admin-panel check: #67 (the «check with Paymob» action), #73.
   #118: ERP PDF downloads (sales invoice URL; WeasyPrint on serverless).
3. Done 2026-11-14: #71 owner password reset, #72 email and phone at signup with a verified email,
   emailed receipts and trial/renewal reminders (mail through Brevo, ADR-004 "Email to owners").

**P2 — The product customers use daily**
4. ETA e-invoicing and e-receipts (legally required in Egypt). **Deferred (2026-11-12)**: no ETA test credentials yet; e-invoice signing (local signer helper vs cloud signing provider) to be decided. E-receipts are the likely first part.
5. **Business activities are placeholders (owner, 2026-11-12).** The global Mizan comes first:
   the shared platform and the `general` modules every workspace uses (POS, sales, inventory,
   purchases, finance and accounting (#25), HR, reports, settings, the screen builder). Activity
   work (ADR-006 phase 8, #106: restaurant onwards, pharmacy, healthcare, hotel, the industry
   audits #24, #36–#58, #113) waits until the owner takes the activities one by one. Retail is
   done; the restaurant start is parked in a git stash. Phase 5 leftovers (POS form layouts,
   copying layouts between roles) belong to the global work.

**P1b — The developer platform (owner, 2026-11-12: a whole product, not on hold)**
ADR-007: milestone 1 = the portal at dev.allmizan.live, the docs, and private declarative
modules (.mzm packages: entities, screens, scopes, extension API, webhooks; SDK and CLI). Code
modules run in sandboxed containers once Mizan moves to its own cluster; marketplace and paid
modules are milestone 2 (#105, paid needs #65).
**Milestone 1 built (2026-11-13), steps 1–7**: the .mzm format and validator, community records and
screens, install from file with scope approval, installation tokens and `/ext/v1`, signed
webhooks with retries, `mizan-sdk` and the `mizan` CLI, and the developer portal with its docs
(website app under `/dev`, `dev.allmizan.live` in production, live since 2026-11-13; English by
default, Arabic on request). Left: publish `mizan-sdk` on PyPI (owner's account; until then the
portal serves the wheel); email verification and password reset for developers can now use
the owners' email code service (#71, #72).

**P1c — Activities as packages, and theme packs (owner, 2026-11-13; ADR-010)**
Every business activity is one folder (`activities/<id>/`: activity.json, modules/, variants/,
themes/, seed), so a developer can build a full Mizan business activity with the framework: the
point Mizan advertises to developers. 1. Done 2026-11-13: all 30 activities moved (149 modules,
5 variants now owned by their activity), backend and screens. 2. Done 2026-11-13: theme packs
(Mizan's six, activities', signed packages from file; one theme per workspace, chosen by its
admin; `mizan theme new`); paid themes with the marketplace. 3. Done 2026-11-13: activity packages
(`mizan activity new`, checked against Mizan's catalogue); running them in a workspace with #107.

**P3 — Platform for outside developers, next**
6. ADR-006 phase 9 (#107): done. Changing between Mizan's activities (2026-11-13) and to a
   developer's activity from the marketplace (2026-11-14, ADR-012: overlay registry, own modules and
   themes installed, updates followed). Later: new workspaces from a developer's activity (with seed
   data), price changes per activity if plans ever depend on it.
7. ADR-006 phase 7 (#105): the marketplace. Done 2026-11-13 for free modules and themes
   (`mizan publish` or the portal → review in the admin panel, countersigned `MZP1` → the store in
   the module centre; ADR-007 milestone 2); activities 2026-11-14 (ADR-012). Next: paid listings
   and payouts after #65.
8. ADR-006 phase 6 (#104): ADR-007 milestone 1 done; the isolation runtime for code modules
   waits for Mizan's own cluster.

**P4 — On-site installs (as customers need them)**
9. Done 2026-11-12: #89 updates, #90 local backups, #92 device limits, #88 in-app network page. Waiting: #88 checks on real tills (owner), #93 Windows signing (deferred), #117 encrypted cloud backup (deferred), #91 own database (designed in ADR-009, not built).

**Ongoing** — healthcare extras (#42–#45). Done: #84 warnings, #83 old docs, #80/#82 tests, #97 vitest workers, #96 storefront switch. Docs refreshed 2026-11-13 (ADR-010 layout, themes, developer platform, domains, roles, security, API).

## 1. Shipped Core & SaaS Milestones (Completed & CI-Green)

- [x] **SaaS Multi-Tenancy Engine** — Row-level security (RLS), tenant isolation (`tenant_id NOT NULL`), composite username constraints, and dynamic subdomain/slug resolution.
- [x] **Admin panel** (`admin/`, English, Mizan team) — "Needs you" queue, workspaces (plan, trial, modules, people, suspend, open as owner, delete), billing with manual "mark paid", team access, live system health, audit log. Rebuilt on real data only (2026-11-09).
- [x] **Owner panel & owner accounts** (`owner/`, Arabic) — one owner, many workspaces; owners sign in at `allmizan.live/login`, employees on their workspace's login page (`<workspace>.allmizan.live/login`); welcome tour after signup; create workspaces; subscribe and pay through Paymob (HMAC-verified, idempotent callbacks). See ADR-004.
- [x] **Plan gating** — tier limits (Starter, Pro, Enterprise), trial expiry to read-only, suspension enforced at sign-in and on every request.
- [x] **Deployment modes: single device and LAN** (ADR-005) — workspaces created as cloud, single device or LAN; Ed25519 licences that work offline and extend on payment; admin Licence tab; server mode for the ERP; **Mizan Setup v1.0.0** for Windows and Linux (guided installer, desktop app, headless installs, bundled PostgreSQL, systemd/Windows service, daily backups, HTTPS + `mizan.local` on the LAN), built and smoke-tested in CI and published to `mizan-releases`. See `installer/README.md`.
- [x] **Deployment modes, follow-ups** — updates with rollback (#89), local backups (#90), licences bound to one computer (#92), the in-app network page (#88).
- [ ] **Deployment modes, remaining** — encrypted cloud backup (#117, deferred), bring your own database (#91, designed in ADR-009), Windows code signing and a manual Windows pass (#93), LAN till checks (#88).
- [x] **Developer platform** (ADR-007) — community modules, `/ext/v1`, signed webhooks, the developer portal and docs at dev.allmizan.live, `mizan-sdk`.
- [x] **Activities as packages and theme packs** (ADR-010) — one folder per activity, theme packs (one per workspace), activity packages for developers.
- [ ] **Billing, remaining** — Paymob production keys and first live payment (#65), subscription lapse (#66), reconciliation (#67), proration (#68), PDF receipts (#69).
- [x] **Tenant Storefronts Engine (`storefront`)** — Public customer-facing storefronts with customizable branding, shopping cart, checkout, coupon engine, and real-time merchant dispatch board (Screens 196–201).
- [x] **In-App Notification Center & Alerts Hub** — TopNav bell popover, live unread badges, automated system alert triggers (storefront web orders, low stock, trial expiry), filter pills, and read/unread state management (Screens 202–205).
- [x] **POS Hardware & Thermal Receipt Module (`pos_hardware`)** — Global continuous barcode listener (`useBarcodeScanner`), 80mm & 58mm ESC/POS thermal printing with Egyptian Tax/ZATCA QR format, and F1–F10 velocity shortcuts modal (Screens 206–209).
- [x] **Background Automation & Cron Worker Module (`automation_worker`)** — Standalone scheduled job worker with CLI support (`python manage.py cron`), midnight shift auto-close with Z-Reports, subscription enforcement, and daily metrics digest (Screens 210–211).
- [x] ~~**HR Biometric Attendance & Device Sync Module (`zk_attendance`)**~~ — removed 2026-11-11 (#110): device sync overwrote hand-entered attendance; another approach will replace it. CSV import stays in HR.
- [x] **Internationalization & Directional Engine (`i18n`)** — Global bilingual switcher (`EN` / `عربي`) with real-time `<html dir="ltr">` / `<html dir="rtl">` layout inversion and complete translation store (Screens 214–215).

---

## 2. Next Major Integration Candidates (Modular Architecture)

Integration modules now live under the **`integrations`** category (`shared/backend/app/integrations/<id>/` + `system/frontend/src/integrations/<id>/`), following the same module contract as core/vertical modules. Each integration is a self-contained, activatable module with its own settings schema, router, models, and UI.

- [x] **WhatsApp Business & Digital Receipt Dispatch (`whatsapp_gateway`)** — Scaffolded as an integration module: settings schema (Cloud API token, phone number ID, template selector, auto-send toggles), message log model, `/integrations/whatsapp/*` endpoints (status, send-receipt, messages), and a management page. Real dispatch to Meta's Cloud API is queued for the worker.
- [ ] **Egyptian Tax Authority (ETA) e-Invoicing & e-Receipt Module (`eta_einvoice`)** — Implement as an `integrations` module: ETA portal submission queue, document signing schema (UUID, issuer tax ID, activity code, 14% VAT + 1% WHT), status dashboard.
- [ ] **Customer Loyalty Points & Tiered Rewards Module (`loyalty_rewards`)** — Implement as an `integrations` module: points per EGP, Bronze/Silver/Gold tiers, in-POS redemption, balance statements.
- [ ] **UI Kit Modernization & Cleanup** — Migrate remaining legacy screen internals from `components/ui.tsx` shim to direct `components/kit/` design system primitives.

---

## 3. Tenant & User Management (Completed)

- [x] **Company Name & Logo Customization** — `store_name`/`logo_url` in store_settings, SettingsPage form, upload-logo endpoint (generates PWA icons).
- [x] **Inner Account & Permission Management** — UsersPage: create users, roles, granular permissions, password reset.
- [x] **Per-User Personal Settings** — `User.settings` jsonb + `/users/me/settings` endpoints + personal section in SettingsPage (theme, language, notification toggles), separate from global store settings.
- [x] **Sector-Specific Settings** — handled via per-module `settings_schema` (SECTOR_MODULES_MAP activates sector-relevant modules, each with its own settings).
