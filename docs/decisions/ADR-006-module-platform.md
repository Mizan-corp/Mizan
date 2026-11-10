# ADR-006: Module platform: activities, variants, roles & screens, marketplace

## Status
Proposed (2026-11-10). Decisions below were agreed with the owner in a structured review
("grilling") on 2026-11-10; the plan is not started. Supersedes the module conventions in
`AGENTS.md` once accepted. Related: #94 (act as one role), #89 (updates), #91/#92.

## Context
Today (audited 2026-11-10):

- `shared/backend/app/modules/` has 48 folders in four layouts (flat, `backend/` subfolder,
  sub-packages, a 24-module `healthcare/` group). Folder name ≠ module id (`printing` = `prn`);
  cryptic ids (`agr`, `bnk`, `cst`…); hyphenated manifest-only stubs (`gym-pos`, `retail-pos`,
  `restaurant-pos`) and an empty `gym_fitness`.
- The core ERP is **not** in modules: `sales`, `inventory`, `finance`, `purchases`, `pos`, `hr`,
  `core` are shells with 0 routes; the real code is 36 routers in `app/api/routers/`.
- Duplicates: gym ×3, restaurant/kitchen_display, pharmacy/phm/healthcare-pharmacy,
  healthcare_clinic vs `healthcare/`; healthcare re-implements accounting, billing, HR,
  inventory, notifications.
- Two loaders: the registry, and hand-written imports in `system_api/router.py` (the registry
  only mounts `hlt_*`/`hot_*`; e.g. `kitchen_display` routes are never served).
- Manifests use ~20 category ids that don't match `categories.json`; pharmacy depends on a
  non-existent `invoicing`.
- **No variants**: one `PosPage.tsx` for every activity.
- Two permission systems: `User.permissions` (`"pos"`, checked by `require_perm`) and
  `sys_roles`/`sys_permissions` (`"inventory.view"`, checked by `authorization.py`). Admins hold
  `"*"` (granted at signup, bootstrap, on-site setup, and injected at sign-in by `auth.py`) and
  `require_perm` lets admin/owner/superadmin roles bypass all checks.
- Positions (98) and roles exist with two layers (platform standard, workspace custom); no
  per-activity layer; no role-specific screens.

## Decisions

### D1. Concepts
| Concept | Meaning |
|---|---|
| **Family** | Organising label only (Health, Food, Commerce…). No behaviour. |
| **Activity** | A business activity (pharmacy, restaurant, school…). Belongs to one family. Defines base modules, roles, positions, terms, settings, demo data. **`general` is a special activity every workspace inherits** (POS, sales, inventory, purchases, finance, HR, contacts, catalog, reports). |
| **Module** | Unit of functionality with a **unique id** and a **home activity**. Owns its data, logic, permissions, screens, widgets, settings. |
| **Variant** | How a module works for a *specific other activity* (`pos` → `pharmacy` variant). `standard` fits every activity unless the module marks otherwise. |
| **Workspace** | One business. Exactly **one activity**, fixed at creation. |

A module from activity A may be used by a workspace of activity B **only if it has a variant
compatible with B** (`standard` counts). A variant changes *how* a module works (screens,
extra fields, rules, terms, defaults, permissions, templates, widgets); anything needing its
own records is a module, which a variant can plug into via `uses`.

### D2. Workspace composition
- On creation: base = `general` defaults + the activity's defaults, each in the activity's
  variant. The owner can add any module of the same family, or any module from another activity
  that has a compatible variant.
- The **variant is fixed by the activity**; owners change only module **settings**.
- **Default modules can be uninstalled** behind a warning listing consequences (dependent
  modules removed too, screens/roles affected) and a typed confirmation (`delete`). The owner
  chooses: delete data now (backup taken first), or keep it hidden for 30 days (reinstall
  restores it).
- **Changing activity** is possible through a guided conversion **approved by the Mizan team**
  (price may change).

### D3. Storage quota
Counts database rows, files, and kept (uninstalled) data. The owner sees it broken down by
module, can free space or export. Warn at 80%; at 100% new uploads are blocked (sales and daily
work never stop); more can be bought.

### D4. People: positions, roles, screens
- **Positions** (job titles) and **roles** (permissions + screens) stay separate; a position
  suggests default roles.
- Three layers, each overriding the previous: platform standard → activity → workspace.
- **Nobody holds everything at once** (#94): the owner assigns roles to a user; the user
  **acts as one role at a time** and switches from the top bar (logged). `"*"` and the role
  bypass are removed; admins get explicit permission sets.
- **One permission system**: permissions are declared in module manifests
  (`pharmacy.dispense`…) and checked by a single `require_perm`.
- **Each role has its own screens**: home, navigation, dashboard, built from screens/widgets
  modules provide. Screen ids resolve through the active variant, so "cashier" sees a drug
  counter in a pharmacy and a floor plan in a restaurant.
- **Full screen builder**: layouts, **custom fields** (stored per workspace, usable in
  reports), and forms. Used by the owner and staff with a `designer` permission.

### D5. Marketplace, developers, pricing
- **Pricing per module**: a base subscription (platform + the activity's default modules,
  users/branches/storage) plus add-on modules, official or community, billed monthly.
- **Community developers** build with the framework and either **publish** (free or paid) to
  the marketplace, or **package privately** and give the file to an owner to install.
- Paid community modules are sold **through Mizan with a revenue share**; Mizan pays developers.
- **Security**: third-party code (published or private) runs **isolated** with "smart
  restrictions": no direct database or process access, only declared scopes through the SDK
  API. On install the owner **approves the scopes** (like phone apps); an update asking for more
  asks again.
- **Third-party UI only through the screen builder** (declarative), never custom JavaScript.
- **Versions**: official modules run the latest version for everyone on the cloud; owners choose
  community module versions. Security-fix policy is an **owner setting** (proposed default:
  apply security fixes automatically; Mizan can always revoke a malicious module from the
  marketplace).
- **On-site installs**: each purchased module is delivered as **one file bound to the
  installation id** (signed, encrypted, not transferable or reversible); installed locally. The
  same local install works on cloud workspaces.

## Target structure

```
shared/backend/app/
├── platform/                 auth, tenancy, permissions engine, i18n, printing, scheduler,
│                             notifications, audit, files, storage quota, custom fields
├── integrations/             whatsapp · zkteco · pos_hardware · paymob · eta_einvoice
├── framework/                module runtime: manifest schema, loader (the only one), variants,
│                             hooks, screens/widgets registry, settings, migrations per module,
│                             isolation host for third-party modules, scopes, licences
├── catalog/families.json     families (labels)
├── activities/<activity_id>/
│   ├── activity.json         family, base modules, roles, positions, terms, settings, nav defaults
│   └── seed.py               demo data
└── modules/<home_activity>/<module_id>/
    ├── manifest.json         id, activity, version, depends_on, permissions, screens, widgets,
    │                         settings schema, fits: [activities] | "all", scopes (3rd party)
    ├── models.py · schemas.py · service.py · router.py · hooks.py · migrations/ · seed.py
    ├── templates/ · tests/ · README.md
    └── variants/<activity_id>/
        ├── variant.json      screens, fields, terms, settings, permissions, uses, templates, widgets
        └── hooks.py          rules for this activity

modules/general/              contacts · catalog · inventory · sales · purchases · finance ·
                              pos · hr · reports      (from app/api/routers/)

system/frontend/src/
├── framework/                screen renderer (builder schemas), role shell, nav from role
└── modules/<home_activity>/<module_id>/
    ├── index.ts              routes, screens, widgets, nav entries
    ├── screens/ · components/ · api.ts
    └── variants/<activity_id>/
```

### Mapping of today's modules
| Today | Target |
|---|---|
| `api/routers/*` + empty shells `core sales inventory purchases finance pos hr contacts` | `modules/general/<area>` |
| `i18n`, `automation_worker` | `platform/` |
| `whatsapp_gateway`, `zk_attendance`, `pos_hardware` | `integrations/` |
| `retail-pos`, `restaurant-pos`, `gym-pos`, `gym_fitness` | deleted; become `pos` variants / activity defaults |
| `kitchen_display` | part of `modules/restaurant/restaurant` |
| `healthcare_clinic`, `healthcare/*` (`hlt_*`) | `modules/<clinic|hospital>/<readable id>`; accounting/billing/hr/inventory/notifications merged into general/platform |
| `hospitality/*` (`hot_*`) | `modules/hotel/<readable id>` |
| `agr bnk cst eng ent fod gov ins oil phm rec prn mfg` | `agriculture banking construction energy events food_manufacturing government insurance oil_gas pharma_manufacturing real_estate printing manufacturing` |

Old ids stay valid through a `legacy_ids` map and a migration of `tenants.active_modules`.

## Developer framework & portal

**SDK** (`mizan-sdk`, Python + a TypeScript screen-schema package) and **CLI**:
`mizan module new | dev | test | build | package | publish`, `mizan variant new`,
`mizan activity new`.
- `dev` runs a local Mizan with the module mounted and a demo workspace per activity.
- `test` runs the module's tests plus the framework's contract checks (manifest schema,
  scopes, Windows-safe names, unique ids, variants resolve, migrations up/down, no raw access).
- `package` produces a signed `.mzm` file; `publish` uploads it for review.

**Developer portal** (new product, `developer/` frontend + API, own domain):
- Accounts and teams; identity/KYC and payout details for sellers.
- Docs, API reference, examples, sandbox workspaces per activity.
- Submissions: automated checks → security review → listing approval; review status and
  feedback; every published version signed by Mizan.
- Listings: description, screenshots, activities/variants supported, scopes, pricing.
- Analytics: installs, revenue, ratings, errors; payouts history.
- Version management, deprecation, emergency revoke; issue reports from owners.

**Owner side**: a marketplace in the owner panel (browse by family/activity, see scopes and
price, install/uninstall, choose versions for community modules, security-fix setting), and
"install from file" for private packages and on-site purchases.

**Admin side**: review queue, developer management, revenue share settings, revocations,
module usage across workspaces.

## Isolation (to be detailed in ADR-007 before phase 6)
Official modules run in-process. Third-party modules run in a separate sandboxed runtime per
module (container or WASM, decided in ADR-007) with no database credentials and no outbound
network except an allow-list; they call Mizan through the SDK API with a per-workspace
capability token limited to the approved scopes; their own data lives in tables the framework
creates for them, still tenant-scoped with RLS; CPU/memory/time quotas and rate limits.

## Plan

Each phase ends usable and tested; nothing breaks existing workspaces.

| Phase | Delivers | Key work |
|---|---|---|
| **0. Finish the bug batch** | #23, #47, #78 + the fixes on `fix/audit-bugs` | Merge, deploy together when needed |
| **1. Framework core** | One loader, manifest schema v2, module ids = folders, `legacy_ids`, families/activities as data | Delete second loader; validate dependencies at startup; Windows-safe/unique checks in CI |
| **2. General activity** | `modules/general/*` from `api/routers/*` | Move code, keep URLs; empty shells removed; platform/ and integrations/ split out |
| **3. One permission system + act as role** | Manifest-declared permissions, single `require_perm`, no `*`/role bypass, role switching | Migration of existing admins/owners to explicit sets; e2e: admin acting as cashier can't reach finance/clinical (#94) |
| **4. Activities & variants** | `activity.json`, variant resolution, hooks; **pharmacy** end to end (POS + inventory variants) | Workspace creation from activity; module install rules (family / compatible variant); uninstall flow with 30-day keep; storage quota |
| **5. Roles with screens & builder** | Role home/nav/dashboard; screen builder with custom fields and forms; `designer` permission | Frontend framework renders screens from schemas; nav from active role |
| **6. Isolation & SDK** | ADR-007; sandbox runtime; scopes; SDK + CLI; private package install (`.mzm`) | Security review of the runtime; on-site per-installation module files |
| **7. Marketplace & developer portal** | Portal, review pipeline, listings, payouts, owner marketplace, admin review | Paymob payouts, revenue share, per-module billing (base + add-ons) |
| **8. Migrate all activities** | Every current module in the new structure with variants; duplicates merged | Activity by activity; demo data per activity |
| **9. Activity change** | Guided conversion with Mizan approval | Price change through billing |

## Consequences
- One way to build anything: the framework the community uses is the one Mizan uses.
- Large migration: most backend and frontend files move; done in phases with legacy ids and
  URL compatibility so existing workspaces and on-site installs keep working.
- Third-party code on the shared cloud is the main risk; it is gated by isolation, scopes,
  review and revocation (ADR-007).
- Per-module pricing replaces plan tiers; existing subscriptions need a mapping.

## Open questions
- Exact sandbox technology and its cost per module (ADR-007).
- Revenue share percentage, payout schedule, developer KYC requirements.
- Base subscription contents and prices per activity; trial rules with add-ons.
- How on-site installs receive official module updates offline (ties to #89).
- What an admin keeps regardless of the acting role (user management, settings?).
