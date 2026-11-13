# ميزان (Mizan) — Roadmap & Delivery Status

Current as of 2026-11-13. **Open work is tracked in [GitHub issues](https://github.com/ammar0xff/Mizan/issues)**; this file is the high-level summary of what has shipped.

## 0. Priority plan (2026-11-11)

Done: ADR-006 phases 1–5 (module platform, permissions and acting roles, activities and variants
with pharmacy end to end, role screens and the screen builder). Open work in priority order;
each step ships, is tested and deployed before the next.

**P0 — Production safety (now)**
1. #114 Uploaded files are lost on Vercel: move them to object storage (needs a provider choice).
2. #64 Apply production migrations from CI, with the backup and schema check `db migrate --production` does.
3. #115 PWA manifest and service worker paths (with a review of `sw.js`); #63 Vercel deploy limit.
4. #85 Manual security follow-ups (owner: change the `platform` password, rotate the Paymob keys).

**P1 — Getting paid and owner basics**
5. #65 Paymob live (waiting on Paymob), then #67 reconciliation, #68 plan changes, #69 PDF receipts, #70 retire the old upgrade flow.
6. #71 owner password reset, #72 verified email and phone, #74 workspace settings, #76 link to the owner panel, #73 owner accounts in admin, #79 website sign-in state.

**P2 — The product customers use daily**
7. Quick cross-cutting fixes: #26 badge contrast, #27 focus rings, #28 tables on small screens, #59/#60 POS touch and keyboard.
8. ETA e-invoicing and e-receipts (legally required in Egypt). **Deferred (2026-11-12)**: no ETA test credentials yet; e-invoice signing (local signer helper vs cloud signing provider) to be decided. E-receipts are the likely first part.
9. **Business activities are placeholders (owner, 2026-11-12).** The global Mizan comes first:
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
(website app under `/dev`, `dev.allmizan.live` in production). Left: attach the domain and give
the website API the signing key at the next deploy; publish `mizan-sdk` on PyPI (owner's
account; until then the portal serves the wheel); email verification and password reset for
developers wait for the mail work (#71, #72).

**P1c — Activities as packages, and theme packs (owner, 2026-11-13; ADR-010)**
Every business activity is one folder (`activities/<id>/`: activity.json, modules/, variants/,
themes/, seed), so a developer can build a full Mizan business activity with the framework: the
point Mizan advertises to developers. 1. Done 2026-11-13: all 30 activities moved (149 modules,
5 variants now owned by their activity), backend and screens. 2. Theme packs: free now (Mizan's,
the activity's, signed packages from file), paid with the marketplace; one theme per workspace,
chosen by its admin. 3. Activity packages in the CLI (declarative until code modules run in
containers); installing them with #107.

**P3 — Platform for outside developers**
10. ADR-006 phase 6 (#104): ADR-007 milestone 1 done (see P1b); the isolation runtime for code modules waits for the own cluster.
11. ADR-006 phase 7 (#105): developer portal and marketplace (needs #65).
12. ADR-006 phase 9 (#107): changing a workspace's activity.

**P4 — On-site installs (as customers need them)**
13. Done 2026-11-12: #89 updates, #90 local backups, #92 device limits, #88 in-app network page. Waiting: #88 checks on real tills (owner), #93 Windows signing (deferred), #117 encrypted cloud backup (deferred), #91 own database (designed in ADR-009, not built).

**Ongoing** — #84 warnings and unused imports, #83 old docs, #80/#82 tests, #97 vitest workers, #96, #61, healthcare extras (#42–#45).

## 1. Shipped Core & SaaS Milestones (Completed & CI-Green)

- [x] **SaaS Multi-Tenancy Engine** — Row-level security (RLS), tenant isolation (`tenant_id NOT NULL`), composite username constraints, and dynamic subdomain/slug resolution.
- [x] **Admin panel** (`admin/`, English, Mizan team) — "Needs you" queue, workspaces (plan, trial, modules, people, suspend, open as owner, delete), billing with manual "mark paid", team access, live system health, audit log. Rebuilt on real data only (2026-11-09).
- [x] **Owner panel & owner accounts** (`owner/`, Arabic) — one owner, many workspaces; owners sign in on the app's `/login`, employees on `/c/<workspace>/login`; welcome tour after signup; create workspaces; subscribe and pay through Paymob (HMAC-verified, idempotent callbacks). See ADR-004.
- [x] **Plan gating** — tier limits (Starter, Pro, Enterprise), trial expiry to read-only, suspension enforced at sign-in and on every request.
- [x] **Deployment modes: single device and LAN** (ADR-005) — workspaces created as cloud, single device or LAN; Ed25519 licences that work offline and extend on payment; admin Licence tab; server mode for the ERP; **Mizan Setup v1.0.0** for Windows and Linux (guided installer, desktop app, headless installs, bundled PostgreSQL, systemd/Windows service, daily backups, HTTPS + `mizan.local` on the LAN), built and smoke-tested in CI and published to `mizan-releases`. See `installer/README.md`.
- [ ] **Deployment modes, remaining** — updates for installed servers (#89), encrypted cloud backup (#90), bring your own database (#91), device limits (#92), Windows code signing and a manual Windows pass (#93), LAN till checks (#88).
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
