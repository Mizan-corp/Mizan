# ADR-006: Module platform: activities, variants, roles & screens, marketplace

## Status

The folder layout below (`modules/<home_activity>/<module_id>/`, variants inside the module)
is superseded by ADR-010: each activity is one folder (`activities/<activity>/modules/`,
`variants/`, `themes/`). Everything else here still holds.

Proposed (2026-11-10). Agreed with the owner in a structured review on 2026-11-10 (the full
question-by-question record is in the **Decision log** at the end). Phases 1–5 are built (see the
implementation notes); 6–9 are not started. Once accepted
it replaces the module conventions in `AGENTS.md`. Related: #94 (act as one role at a time),
#89 (updates for installed servers), #91 (bring your own database), #92 (device limits).

## Goals (as set by the owner)
1. **Customise every business activity.**
2. **Use a module from one business activity in another.**
3. **User management with positions and roles, unique per business activity if wanted.**
4. **Every role or position has its own custom screen.**

Plus: a **development framework** for families and modules that Mizan and **community
developers** both use; a **marketplace** where developers publish and sell modules; owners
install them, or install privately packaged modules.

## Context: what exists today (audited 2026-11-10)

### Module structure
- `shared/backend/app/modules/` has 48 folders in **four layouts**:
  - flat: `manifest.json` + `models.py` + `router.py`, the most common
  - code in a `backend/` subfolder: `healthcare_clinic/`
  - one module with sub-packages: `hospitality/` (`hotel_pms`, `housekeeping`, `night_audit`, …)
  - a group folder holding 24 modules: `healthcare/` (`hlt_*` ids)
- Frontend: `system/frontend/src/modules/` (39 folders) roughly mirrors it; core ERP screens
  live separately in `src/features/`.
- **The core ERP is not in modules.** `core`, `sales`, `inventory`, `finance`, `purchases`,
  `pos`, `hr` are module shells with **0 routes**; the real code is 36 routers in
  `app/api/routers/`. "Modules are plug-ins" holds only for industry modules.
- **Duplicates / overlaps**:
  - gym: `gym`, `gym_fitness`, `gym-pos`
  - restaurant: `restaurant`, `restaurant-pos`, `kitchen_display`
  - pharmacy: `pharmacy` (retail), `phm` (pharma manufacturing), `healthcare/pharmacy`
  - clinic vs hospital: `healthcare_clinic` vs the `healthcare/` group, whose modules
    re-implement accounting, billing, HR, inventory and notifications.
- **Stubs**: `gym_fitness`, `gym-pos`, `restaurant-pos` and `retail-pos` have only a
  manifest. A hyphen can't be part of a Python package name.
- **Naming**: cryptic ids (`agr bnk cst eng ent fod gov ins oil phm rec mfg`), and folder ≠ id
  (`printing` holds `prn`). Platform features (`i18n`, `automation_worker`) and integrations
  (`whatsapp_gateway`, `zk_attendance`, `pos_hardware`) sit next to business modules.
- **Two loaders**: the registry, and hand-written imports in `system_api/router.py`. The
  registry only mounts `hlt_*`/`hot_*`, so e.g. the `kitchen_display` routes are never served.
- **Metadata**:
  - Manifests use about 20 category ids that don't match the 11 in `categories.json`.
  - `pharmacy` depends on `invoicing`, which doesn't exist.
- **No variants**: one `PosPage.tsx` for every activity. The README's "a restaurant sees a
  floor plan, a pharmacy a drug search" is not implemented.
- Activities exist only as a list of names (`core/sectors.py`, 30+) selecting modules and demo
  data.

### People and access
- **Two permission systems**:
  - `User.permissions` (`"pos"`, `"finance"`), checked by `require_perm`
  - `sys_roles` / `sys_permissions` (`"inventory.view"`), checked by `authorization.py`
- **Admins hold everything at once**:
  - they get `"*"` at signup (`services/workspaces.py`), in the bootstrap and in on-site setup
  - `auth.py` adds `"*"` at sign-in for any admin or owner who lacks it
  - since `9964b65`, `require_perm` lets the admin/owner/superadmin roles bypass every check
    (it replaced a username backdoor)
  - the clinic module and `shifts.py` have their own admin shortcuts
- The docs and the app's `can()` say "permissions decide, never role names" and promise
  clinical isolation from non-clinical staff.
- 98 standard positions and the standard roles exist, in two layers: platform (`tenant_id` null)
  and workspace custom. There is **no per-activity layer** and **no role-specific screens**:
  everyone gets the same dashboard and navigation, filtered by permissions.

### Status against the goals
| Goal | Today |
|---|---|
| 1. Customise an activity | Partial: an activity only picks modules and demo data |
| 2. Module across activities | Mostly possible, but some code checks the activity, not the module |
| 3. Positions/roles per activity | No activity layer; two permission systems |
| 4. Screen per role/position | Missing |

## Decisions

### D1. Concepts

| Concept | Meaning |
|---|---|
| **Family** | Organising label only (Health, Food, Commerce, …): browsing and grouping. No behaviour. |
| **Activity** | A business activity (pharmacy, restaurant, school, …). Belongs to one family. Defines base modules, positions, roles, role screens, terms, settings, demo data. |
| **`general`** | A special activity that **every activity inherits**: contacts, catalog, inventory, sales, purchases, finance, POS, HR, reports. |
| **Module** | A unit of functionality with a **unique id** and a **home activity**. It owns its data, logic, permissions, screens, widgets and settings. |
| **Variant** | How a module works **for a specific activity**, e.g. the `pos` module's `pharmacy` variant. `standard` fits every activity unless the module says otherwise. An activity from one family may have a variant for an activity of another family. |
| **Workspace** | One business with **exactly one activity**, fixed at creation. |

**Variant or module?**
- A **variant** changes *how* a module works for an activity: same data, plus extra fields.
- Anything that needs its **own records** (tables, kitchen tickets, prescriptions, rooms) is a
  **module**, which a variant can plug into through `uses`.
- So `restaurant` is a module, while "restaurant POS" is a variant of `pos` that uses it.

**What a variant can change (`variant.json` + `hooks.py`):**

| Part | Example: the pharmacy variant of POS |
|---|---|
| **screens**: replace or add | checkout becomes a drug-search counter |
| **fields**: extra fields on the module's records | sale line: batch, expiry, prescription number |
| **rules** (`hooks.py`): validation, side effects | no prescription drug without a prescription |
| **uses**: other modules it plugs into | `pharmacy` (batches); restaurant POS uses `restaurant` (tables, kitchen) |
| **terms** | "item" → "دواء", "customer" → "مريض" |
| **settings**: defaults | FEFO on, sell by strip or box |
| **permissions**: extra | `pos.dispense_controlled` |
| **print templates** | receipt shows batch and expiry |
| **widgets** | "expiring this month" |

**Example: POS and its variants**

```
modules/general/pos/
├── manifest.json        variants: standard, retail, restaurant, pharmacy, salon
├── models.py            one sales/shift model for every variant
├── service.py · router.py
├── hooks.py             extension points: before_add_item, before_confirm, after_confirm…
└── variants/
    ├── standard/   variant.json
    ├── retail/     variant.json   fast-scan layout, barcode first, F-keys
    ├── restaurant/ variant.json   uses: restaurant (tables, kitchen)
    │               hooks.py       after_confirm → send a ticket to the kitchen
    └── pharmacy/   variant.json   search by scientific name, batch by expiry (FEFO)
                    hooks.py       before_confirm → prescription required for flagged drugs
```

### D2. How a workspace is composed

1. **At creation** the workspace takes its activity's required modules, from any activity, each
   in a **compatible variant** (`standard` counts):
   - **base** = `general` defaults + the activity's defaults
2. **Adding modules**: the owner can extend from the base to
   - any module in the activity's **family**, or
   - a module from **another activity** if it has a compatible variant for this activity.
3. **The variant is fixed by the activity.** Owners cannot change it; they change each
   module's **settings** (every module has settings).
4. **Default modules can be uninstalled**:
   - behind a warning listing the consequences: dependent modules removed too, roles and
     screens that use them
   - plus a security check: typing `delete`
   - then the owner chooses: **delete the data** (immediately, after a backup), or **keep it
     hidden for 30 days** (reinstalling restores it).
5. **Changing activity** is possible through a **guided conversion**:
   - variants swapped, data mapped
   - **approved by the Mizan team**, since the price may differ

**Resolution order**: module (base) → variant (chosen by the activity) → workspace settings,
custom fields, role screens.

**Example: `activities/pharmacy/activity.json`**

```json
{
  "id": "pharmacy",
  "family": "health",
  "modules": {
    "pos": "pharmacy", "inventory": "pharmacy", "sales": "standard",
    "purchases": "standard", "finance": "standard", "contacts": "standard",
    "pharmacy": "standard"
  },
  "optional": ["hr", "whatsapp"],
  "terms": { "customer": "مريض", "item": "دواء" },
  "positions": ["pharmacist", "pharmacy_assistant", "cashier", "store_keeper"],
  "roles": {
    "pharmacist": {
      "permissions": ["pos.sell", "pharmacy.dispense", "pharmacy.batches.view"],
      "home": "pos.checkout",
      "nav": ["pos.checkout", "pharmacy.prescriptions", "sales.returns"],
      "dashboard": ["pharmacy.expiring_soon", "sales.today"]
    }
  },
  "settings": { "inventory.fefo": true }
}
```

### D3. Storage quota (cloud, where Mizan provides storage)
- **What counts**: database rows, files, and kept (uninstalled) data.
- **The owner sees it analysed by module**, and can free space or export it.
- **Limits**: a warning at 80%. At 100% new uploads are blocked, while sales and daily work
  never stop. More can be bought.

### D4. People: positions, roles and screens
- **Positions** (job titles: pharmacist, chief accountant) and **roles** (permissions +
  screens) **stay separate**; a position suggests default roles.
- **Three layers**, each overriding the one before:

  ```
  platform     standard positions, roles, permissions
     ↓
  activity     pharmacy adds "pharmacist", hides what it doesn't need, renames terms
     ↓
  workspace    the owner creates/edits positions and roles, picks each role's screens
  ```
- **Nobody holds everything at once.** A workspace super admin does not get all permissions; they
  **act as a role** (doctor, HR, accountant, cashier…), one at a time.
  - The **owner assigns roles to users** in the workspace settings.
  - The **user switches between their assigned roles** from the top bar; every switch is logged.
  - `"*"` and the role bypass are removed; admins get explicit permission sets (#94).
- **One permission system**: permissions are declared in module manifests
  (`pharmacy.dispense`…) and checked by one `require_perm`. Clinical isolation holds.
- **Every role has its own screens**: home, navigation and dashboard, assembled from the screens
  and widgets that modules and variants provide.
  - Screen ids resolve through the active variant: the same "cashier" role gets a drug counter
    in a pharmacy and a floor plan in a restaurant.
- **A full screen builder**:
  - **what it changes**: layouts, **custom fields** (stored per workspace, usable in reports)
    and **forms**
  - **who uses it**: the owner, and staff the owner gives a **`designer`** permission

### D5. Development framework, marketplace, pricing

**Pricing**
- **Per module**: a **base subscription** (the platform plus the activity's default modules;
  users, branches and storage) plus **add-on modules**, official or community, billed monthly.
- This replaces today's plan tiers (`core/plans.py`); existing subscriptions are mapped.

**Who builds what**
- **One framework for everyone**: it scaffolds families, activities, modules and variants. Mizan
  builds with it, and so do **community developers**.
- **Developers either**:
  - **publish** to the marketplace (free or paid), and owners install from it; or
  - **package privately** and hand the file to an owner, who installs it locally. Private
    installs are allowed **anywhere** (cloud included), made safe by isolation and smart
    restrictions.
- **Paid community modules are sold through Mizan** with a revenue share. The owner pays Mizan
  (Paymob); Mizan pays developers.

**Security**
- **Isolation**: third-party code runs **isolated**, with "smart restrictions": no database
  credentials or process access, only its declared scopes through the SDK API (see Isolation).
- **Scopes**: on install, the owner **sees and approves the module's scopes**, like phone apps.
  An update that asks for more asks again.
- **No custom JavaScript**: third-party screens are **built with the screen builder only**
  (declarative); they can't steal sessions.

**Versions**
- **Official modules**: everyone on the cloud runs the latest version.
- **Community modules**: owners choose the version, and several versions can run side by side.
- **Security fixes**: decided by the **owner, through a setting**.
  - Proposed default: apply security fixes automatically.
  - Mizan can always pull a malicious module from the marketplace.

**On-site installs** (single device / LAN)
- Each purchased module is exported to the owner as **one file bound to the installation id**:
  signed and encrypted, it can't be reversed or installed on another instance.
- Installation is local. Installing from a file works on cloud workspaces too.

## Target structure

```
shared/backend/app/
├── platform/                 the engine, never switched off: auth, tenancy, permissions
│                             engine, i18n, printing, scheduler (automation_worker),
│                             notifications, audit, files, storage quota, custom fields
├── integrations/             whatsapp · zkteco · pos_hardware · paymob · eta_einvoice
├── framework/                module runtime: manifest schema, the only loader, variant
│                             resolution, hooks, screens/widgets registry, settings,
│                             per-module migrations, scopes, licences, isolation host
├── catalog/families.json     families (labels)
├── activities/<activity_id>/
│   ├── activity.json         family, base modules + variants, positions, roles (permissions,
│   │                         home, nav, dashboard), terms, settings
│   └── seed.py               demo data
└── modules/<home_activity>/<module_id>/
    ├── manifest.json         id (= folder), activity, version, depends_on, permissions,
    │                         screens, widgets, settings schema, fits ("all" | activities),
    │                         scopes (third party)
    ├── models.py · schemas.py · service.py (logic, not in the router) · router.py
    ├── hooks.py · migrations/ · seed.py · templates/ · tests/ · README.md
    └── variants/<activity_id>/
        ├── variant.json
        └── hooks.py

modules/general/              contacts · catalog · inventory · sales · purchases · finance ·
                              pos · hr · reports       (from app/api/routers/)

system/frontend/src/
├── framework/                screen renderer (builder schemas), role shell, navigation and
│                             home built from the active role
└── modules/<home_activity>/<module_id>/
    ├── index.ts              routes, screens, widgets, nav entries (App.tsx and nav.ts stop
    │                         listing modules by hand)
    ├── screens/ · components/ · api.ts
    └── variants/<activity_id>/   screens/components replacing or adding to the base
```

### Mapping of today's modules
| Today | Target | Why |
|---|---|---|
| `api/routers/*` + the empty shells `core sales inventory purchases finance pos hr contacts` | `modules/general/<area>` | The real code is in `api/routers` |
| `i18n`, `automation_worker` | `platform/` | Engines, not business modules |
| `whatsapp_gateway`, `pos_hardware` | `integrations/` | Connectors (`zk_attendance` removed, #110) |
| `retail-pos`, `restaurant-pos`, `gym-pos`, `gym_fitness` | deleted; become POS variants / activity defaults | Manifest-only stubs |
| `kitchen_display` | part of `modules/restaurant/restaurant` | Part of the restaurant |
| `healthcare_clinic` | `modules/clinic/clinic` | One layout |
| `healthcare/*` (`hlt_*`) | `modules/hospital/<readable id>`; `hlt_pharmacy` → `hospital_pharmacy` | Readable, no clash with retail `pharmacy` |
| `healthcare/accounting`, `billing`, `hr_workforce`, `inventory_procurement`, `notifications` | merged into `general` finance/hr/inventory and `platform/notifications` (as variants where clinical) | They duplicate the core |
| `hospitality/*` (`hot_*`) | `modules/hotel/<readable id>` | Readable ids |
| `agr bnk cst eng ent fod gov ins oil phm rec prn mfg` | `agriculture banking construction energy events food_manufacturing government insurance oil_gas pharma_manufacturing real_estate printing manufacturing` | Readable; folder = id |

### Rules that keep it correct (enforced by tests/CI)
- **Folder name = module id**, unique, readable, valid on Windows (installers are built there).
- **IDs never break workspaces**: a `legacy_ids` map (`prn` → `printing`, `hlt_emr` → `emr`…)
  plus a migration of `tenants.active_modules`.
- **Families and categories come from one list**; the ~20 ad-hoc category ids disappear.
- **Dependencies are validated at startup** (a missing one like `invoicing` fails the build).
- **One loader** only (no hand-written module imports).
- **Every module declares its permissions, screens and settings**; nothing checks the activity
  name directly.

## Developer framework & portal

### SDK and CLI
- **Packages**: `mizan-sdk`, Python, plus a TypeScript screen-schema package.
- **Commands**:
  - `mizan family new` · `mizan activity new` · `mizan module new` · `mizan variant new`
  - `mizan dev`: a local Mizan with the module mounted and a demo workspace per activity
  - `mizan test`: the module's tests plus the framework's contract checks: manifest schema,
    scopes, Windows-safe names, unique ids, variants resolve, migrations up and down, no raw
    database access
  - `mizan build` / `mizan package`: a signed `.mzm` file
  - `mizan publish`: uploads it for review

### Developer portal
A new product: `developer/` frontend + API, on its own domain.
- **Accounts and teams**: identity verification and payout details for sellers.
- **Learning**: docs, API reference, examples, sandbox workspaces per activity.
- **Submissions**: automated checks → security review → listing approval. Developers see
  review status and feedback; every published version is signed by Mizan.
- **Listings**: description, screenshots, supported activities and variants, scopes, price.
- **Analytics**: installs, revenue, ratings, error reports, payout history.
- **Versions**: management and deprecation; emergency revoke.

### Owner side (owner panel)
- **Marketplace**: browse by family and activity; see scopes and price; install and uninstall
  (with the D2 flow); choose community module versions; the security-fix setting.
- **Install from file**: for private packages and on-site purchases.
- **Storage**: usage and its analysis (D3).
- **Workspace settings**: roles, positions and role assignment (D4).

### Admin side (admin panel)
- Review queue, developer management, revenue-share settings, revocations.
- Module usage across workspaces.
- Approving activity changes (D2).

## Isolation (detailed in ADR-007 before phase 6)
- **Official modules** run in-process.
- **Third-party modules** (published or private) run in a separate **sandboxed runtime per
  module** (container or WASM, chosen in ADR-007):
  - no database credentials, no access to other processes
  - no outbound network except an allow-list
  - they call Mizan only through the SDK API, with a per-workspace capability token limited to
    the approved scopes
  - their own data lives in framework-created tables: tenant-scoped, under RLS, counted in the
    storage quota
  - CPU, memory and time quotas, and rate limits
  - signed versions only

## Plan

Each phase ends usable and tested; existing workspaces and on-site installs keep working.

| Phase | Delivers | Key work |
|---|---|---|
| **0. Finish the bug batch** | #47, #78; the fixes on `fix/audit-bugs` (#17–#23, #81, migration v49) | Re-run e2e; merge and deploy together when needed |
| **1. Framework core** | One loader; manifest schema v2; folder = id; `legacy_ids`; families and activities as data | Remove the second loader; startup dependency validation; CI checks (names, ids) |
| **2. General activity** | `modules/general/*` from `api/routers/*`; `platform/` and `integrations/` split out | Move code, keep URLs; delete empty shells and stubs |
| **3. One permission system + act as a role** | Manifest-declared permissions, one `require_perm`; no `"*"` or role bypass; owner assigns roles, user switches | Migrate admins/owners to explicit sets; e2e: an admin acting as cashier can't reach finance or clinical records (#94) |
| **4. Activities & variants** | `activity.json`, variant resolution, hooks; **pharmacy end to end** (POS + inventory variants) | Workspace creation from the activity; install rules (family / compatible variant); uninstall flow with 30-day keep; storage quota and its analysis |
| **5. Role screens & builder** | Role home/navigation/dashboard; screen builder with custom fields and forms; `designer` permission | Frontend framework renders builder schemas; navigation from the active role |
| **6. Isolation & SDK** | ADR-007; sandbox runtime; scopes and owner approval; SDK + CLI; private `.mzm` installs | Security review of the runtime; on-site per-installation module files |
| **7. Marketplace & developer portal** | Portal, review pipeline, listings, payouts; owner marketplace; admin review queue | Per-module billing (base + add-ons); Paymob payouts and revenue share |
| **8. Migrate every activity** | All current modules in the new structure, with variants; duplicates merged | Activity by activity, with demo data per activity |
| **9. Activity change** | Guided conversion, approved by the Mizan team | Price change through billing |

## Consequences
- **One way to build anything**: the framework the community uses is the one Mizan uses.
- **A large migration**: most backend and frontend files move. It happens in phases, with legacy
  ids and URL compatibility.
- **Third-party code on the shared cloud is the main risk**: isolation, scopes, review, signing
  and revocation gate it.
- **Per-module pricing replaces plan tiers**: existing subscriptions are mapped.

## Open questions
- **Isolation**: the sandbox technology and its cost per module (ADR-007).
- **Commercial**:
  - the revenue-share percentage, payout schedule and developer verification
  - base subscription contents and prices per activity; trials with add-ons
- **Offline updates**: how on-site installs get official module updates (#89).
- **Uninstall**: whether "delete data now" still keeps a short safety backup the owner can
  restore.

## Phase 1 implementation notes (2026-11-10)
Choices made while implementing phase 1 (#99), for review:
- **Families** (`app/catalog/families.json`): general, commerce, food & hospitality, health,
  education, services, logistics, industry, projects/real estate/energy, financial & public
  institutions. Each of the 35 existing activities is assigned to one (`app/activities/<id>/activity.json`); the
  five legacy sectors (`services`, `plumbing`, `electrical`, `tiles`, `paint`) are marked
  `legacy_of` their current activity.
- **Manifest v2** adds `activity` and `kind` (`business` | `platform` | `integration`) and drops
  `category`: a module's family is its activity's. Platform/integration modules stay in
  `modules/` until phase 2 moves them to `platform/` and `integrations/`.
- **Readable ids now** for the top-level modules (`prn`→`printing`, `agr`→`agriculture`, …,
  `ent`→`events`, `mfg`→`manufacturing`); URLs (`/prn`, `/agr`…) and table names are unchanged.
  The hospital and hotel modules lost their `hlt_*`/`hot_*` prefixes too (owner's decision:
  full names now); clashes resolved as `hospital_pharmacy`, `health_insurance`,
  `medical_billing`, `medical_accounting`, `patient_notifications`, `medical_workforce`,
  `medical_supplies`, `hospital_analytics`, `hotel_pms`. Merging duplicates is still phase 8.
- **Activities are one full word** (owner's decision): `discrete_mfg`→`manufacturing`,
  `food_mfg`→`food`, `pharma_mfg`→`pharmaceuticals`, `wms_3pl`→`warehousing`,
  `law_firm`→`legal`, `field_service`→`maintenance`, `oil_gas`→`petroleum`,
  `real_estate`→`property` (migration v52 rewrites stored sectors; `legacy_activities` keeps the
  old ids accepted).
- **Planned modules from the SRS**: every module the SRS names that isn't built has the full
  standard structure with `"status": "planned"` (not mounted or offered), a `README.md` with the
  SRS requirements it covers and where related code lives today, and `srs` ids in its manifest: e.g. `restaurant/menu`,
  `pharmacy/drug_interactions`, `school/timetable`, the banking, insurance, government,
  entertainment and petroleum modules (grouped from the SRS requirement lists), the shared
  `general/*` engines (XMOD), `platform/marketplace`, `platform/customization`,
  `integrations/{webhooks,fawry,instapay}`.
- **Business presets** keep their ids (`prn`, `cst`…): they are a separate namespace stored in
  the workspace's settings; only the module lists inside them were renamed.
- The manifest-only stubs (`retail-pos`, `restaurant-pos`, `gym-pos`, `gym_fitness`) were
  removed now; their ids map to `pos`, `restaurant`, `gym`. `operations` got a manifest so
  activities only list real modules.
- **Migrations**: v50 (active modules in `tenants.active_modules` only), v51 and v52 (old module
  and activity ids rewritten in stored sectors, module lists and module settings keys).
- **Folder layout applied** (backend and frontend): `modules/<home_activity>/<module_id>/`,
  `platform/<id>/`, `integrations/<id>/`, `framework/loader.py`, `activities/<id>/activity.json`;
  the frontend mirrors it (`src/modules/<activity>/<module>/`, `src/platform/`,
  `src/integrations/`). `modules/healthcare/` also keeps shared healthcare code (`models.py`,
  `seeder.py`) until phase 8. The healthcare modules' `backend/` subfolders were flattened.
- **The module standard** is written in `docs/MODULE_STANDARD.md` and defined once as files in
  `app/framework/module_template/`, which the scaffold generates from.
- **Full layout scaffolded** (`app/framework/scaffold.py`, `python manage.py module
  new|scaffold|check`, enforced by tests): every module has `schemas.py`, `service.py`,
  `hooks.py`, `seed.py`, `migrations/`, `templates/`, `tests/`, `variants/standard/`, and on the
  frontend `index.ts` (a `ModuleDefinition`, collected by `src/framework/registry.ts`), `api.ts`,
  `screens/`, `components/`, `variants/`. Files with nothing in them yet say where the code still
  is: logic still in `router.py` moves to `service.py` when a module is reworked (general in
  phase 2, the rest in phase 8); demo data moves from `services/demo_seed.py` to each `seed.py`.
- **Variants from this ADR's examples** are recorded as `planned`: POS `retail`, `restaurant`,
  `pharmacy`, `salon`; inventory `pharmacy`. Activities name the variant each module runs in
  (`variants`), plus `optional`, `terms`, `positions`, `roles`, `settings` (empty unless the ADR
  gave them: pharmacy's terms and FEFO setting).
- **Framework and platform placeholders**: `framework/{manifest,variants,hooks,screens,settings,
  migrations,scopes,isolation,licences}.py`; `platform/{auth,tenancy,permissions,printing,
  notifications,audit,files}` describe engines that move there in phase 2; `storage_quota` and
  `custom_fields` are still to build; `integrations/{paymob,eta_einvoice}`.

- **Phase 2 started (core ERP into modules)**: `app/api/routers/*` and `app/services/*` moved into
  `modules/general/<module>/` (`routes/<area>.py` combined by `router.py`; `service.py` or
  `services/<area>.py`), the platform engines into `platform/<engine>/` (auth, permissions,
  notifications, printing, settings, billing, updates, archive, audit, licensing, tenancy), Paymob
  into `integrations/paymob/`; `app/api/` is gone. The module centre is the `marketplace` platform
  module and the fixed reports the `reporting` module (both now active). URLs unchanged; removed:
  the unused duplicate mounts under `/modules/<core module>/…` and `/modules/core/…`, and the
  retired `/payroll` router that was still reachable through them (its tables were dropped).
  Then `core/`'s engines moved too: security → `platform/auth`, tenancy → `platform/tenancy/context.py`,
  authorization/RBAC catalogue/roles → `platform/permissions`, printing engine → `platform/printing`,
  licence keys → `platform/licensing`, releases → `platform/updates`, plans → `platform/billing`,
  sectors → `catalog/`, module activation and presets → `framework/activation.py`. `core/` keeps only
  the kernel: config, exceptions, pagination, rate limiting. Then the data models and schemas:
  `app/models/*` and `app/schemas/*` moved into their module (`models.py` or `models/<area>.py`,
  same for schemas) or platform engine (users and owners → `platform/auth`, tenants →
  `platform/tenancy`, access tables → `platform/permissions`, …); `app/models/` keeps only the
  model registry and the migrations table. Then logic left in route functions moved to services (finance safes/expenses/
  wallets, contacts payments, operations, quotations, inventory warehouses, HR employees and
  attendance, invoices), fixing the money and stock bugs found on the way; and demo data moved from
  `services/demo_seed.py` into the modules' and activities' `seed.py`, run by `framework/demo.py`
  (same data for every activity that had a catalogue; others now get the retail catalogue instead
  of the plumbing one). `app/services/` is gone.

## Phase 3 implementation notes (2026-11-11)
One permission system and acting as one role (#101, #94). Answers given by the owner:
- **An admin acting as another role keeps nothing extra.** Acting as cashier means only the
  cashier's permissions; managing users or settings needs switching back (one click in the top
  bar). This resolves the open question "admin rights".
- **Permission names are the current area names** (`pos`, `sales`, `quotations`, `customers`,
  `inventory`, `purchases`, `operations`, `finance`, `payroll`, `reports`, `users`, `settings`,
  `admin`, `archive`, `shifts`, the clinic ones), plus `supervise` (every branch and shift, which
  used to come from the `manager` role name). Each is declared in the owning module's manifest
  (`"permissions": [{"id", "name", "name_en"}]`). Finer names (`inventory.manage`…) can come
  later, module by module.
- **Existing users keep exactly their access.** Migration v54 gives each user the standard role
  for their role name when it matches their access exactly, otherwise a workspace role of their
  own (`<role>-<uid8>`, "cashier — Ahmed"). Admins and owners get the admin role, which lists
  every declared permission explicitly. Verified locally: 165 users, 0 differences.

How it works:
- `sys_roles.grants` holds a role's permissions (v53). Standard roles have no workspace, are
  synced from `roles.py` once per process (in a session with no workspace bound), and workspaces
  can read them but not change them. Workspaces create their own roles.
- `user_role_assignments` lists a user's roles; `users.active_role_id` is the one they act as.
  `get_current_user` loads the acting role; `require_perm` and the clinic checks look only at its
  permissions. There is no `"*"`, and no role name grants anything.
- `POST /auth/me/acting-role` switches role (logged as `switch_role`); `/auth/me` returns
  `acting_role` and `roles`. The top bar shows "العمل بدور" when a user has more than one role.
- `/authz/access/{permissions,roles,roles/{id},users/{id}/roles}`: roles and assignments, with
  the `users` permission. **No escalation**: you can only create, edit, delete or assign roles
  within the permissions of the role you act as now. Standard roles can't be edited.
- `PUT /permissions/{id}` (the users screen's checklist) still works: a list equal to the
  standard role assigns it, otherwise it becomes the user's own role.
- **One access screen** (users): each user's position, acting role and assigned roles. The older
  "advanced" screen was removed (2026-11-11): its policy engine was never called by any endpoint,
  so permission overrides, catalogue roles, facility/patient rules and break-glass enforced
  nothing. Their tables stay; real patient-level clinical access is #113.
- **Positions per activity** (D4's three layers): `app/activities/general/positions.json` holds
  the positions every business has; each activity adds its own in
  `app/activities/<activity>/positions.json` (a pharmacy's pharmacists, a restaurant's chefs and
  waiters, a hospital's medical staff); a workspace can add more. Legacy activities use the
  positions of the activity they map to. Each position lists `suggested_roles` (standard role
  codes); picking a position on the users screen pre-ticks them, but only roles grant access.
  Standard positions are rows with no workspace keyed by (activity, code) (v58), synced from the
  files once per process.
- Migrations can now be Python steps (`"python:module:function"`), run by the app's runner and
  by `manage.py db migrate` (inside the system API container).
- Everything runs under workspace isolation by the database role (#112): a request's
  transactions use `mizan_app`, so platform rows such as standard roles are written in a separate
  session.

## Phase 4 implementation notes (2026-11-11)
Activities and variants, pharmacy end to end (#102). The owner's answers: pharmacy selling is the
POS's `pharmacy` variant (dispensing is a sale), and fields are fully customisable.

- **Variants** (`framework/variants.py`): the activity picks each module's variant
  (`activity.json` "variants"); a variant still "planned" falls back to `standard`. Terms and
  setting defaults resolve variant -> activity.
- **Hooks** (`framework/hooks.py`): a module calls `emit("<module>.<moment>", db, ...)`; only the
  workspace's variant's `hooks.py` runs. Used: `inventory.after_movement` and
  `pos.before_confirm` / `pos.after_confirm`.
- **Fields** (`framework/fields.py`): products, sales, sale lines, customers, suppliers and
  purchase lines have an `extra` JSON column (v60). A variant declares default fields; the
  workspace overrides, hides or adds its own (`workspace_fields`, `/settings/fields/...`).
  Values are validated (types, required, unknown keys refused, read-only ones set by rules only).
  `/settings/workspace-profile` gives the app the activity, variants, terms and fields.
- **One stock path**: `inventory.apply_movement` is the only way stock changes. Consolidating it
  found that goods receipts and branch transfers never updated balances (none in production).
- **Batches** (module `batches`, v61): lots per product, branch and batch number with expiry;
  first-expiry-first-out; expired and quarantined stock is never sold; transfers keep the batch;
  cancellations and returns go back to their batch; lots always equal stock.
- **Pharmacy**: drugs are products with the inventory variant's fields; the POS variant requires
  the prescriber and patient for prescription-only drugs (plus national ID and licence for
  controlled ones), records the prescription against the sale (v62) and logs controlled
  dispensing with its batch; receipts print each line's batch and expiry. v63 moved the pharmacy's
  own drugs and batches into products, stock and lots; the old dispensing endpoint answers 410.
  Clinic dispensing goes through the same stock path.
- **Composition** (`framework/composition.py`): new workspaces start with `general`'s defaults
  plus the activity's; modules can be added from `general`, the activity, its family, or another
  activity's module with a variant for it. Removal: preview, typed `delete`, keep 30 days
  (reinstall restores; nightly purge) or delete now after an export stored with the record
  (v64). Core ERP data is never deleted; modules the activity's variants `use` can't be removed.
  "Apply preset" is retired.
- **Storage** (`framework/storage.py`, v65): rows x average row size per table, grouped by
  module, plus kept data, exports and files; nightly measurement with an 80% warning; uploads are
  refused at 100% while daily work continues. Shown in the owner panel by module.
- **Known gaps**: uploaded files are written to the API's disk, which isn't kept on Vercel; POS
  variants other than pharmacy (retail, restaurant, salon) are still "planned"; insurance
  co-pay at the POS is not built.

## Phase 5 implementation notes (2026-11-11)
Role screens and the screen builder (#103). The owner chose: every activity's menu converted now,
and a builder covering role layouts, custom fields, form layouts and a dashboard widget catalogue.

- **Screens are declared**: the hand-typed menus (`lib/nav.ts`, one per activity) became data. 77
  screens in module manifests (`"screens": [{"id", "path", "label", "icon", "permission"}]`), each
  activity's menu in `activity.json` (`"menu"`: groups of `{"screen", "label"?, "icon"?}`;
  `general`'s is the default). A screen's permission is its own: a menu arranges and renames
  screens, it never changes who sees them (the two entries that overrode a permission were folded
  into their screens). The app only maps icon names to components.
- **What a role sees** (`framework/screens.py`, `GET /settings/screens`): the workspace's layout for
  the acting role, else the activity's for that role (`activity.json` "roles"), else the
  activity's, else general's; then only screens and widgets of installed modules that the role's
  permissions allow. `core` and `reporting` count as always installed (their routes have no
  module guard). The sidebar, rail, top bar, command palette and the "no access" fallback all use it.
- **Widgets**: modules declare them (`"widgets": [{"id", "label", "permission", "size": s|m|l}]`)
  and register their components in `index.ts`; the dashboard renders the role's list (an entry can
  set its own size). The old dashboard was split into reporting (today, month, 14-day trend),
  POS (shift, latest invoices), inventory (shortage count and list) and batches (expiring). The
  trend comes from a new `/reports/sales/trend` (it was built from the last 14 invoices).
- **Layouts are per workspace** (`workspace_layouts`, v66, RLS): kind `role` (target: role id) and
  `form` (target: record). Standard roles are platform rows shared by every workspace, so their
  layouts can't live on `sys_roles` (the first draft of v66 did that; it never reached production).
- **The builder** (`/designer`, `platform/settings/designer.py`), gated by the `designer`
  permission (admins hold every declared permission, so owners have it):
  - *role screens*: main screen, menu groups (add, rename, order, move screens between groups,
    rename screens) and dashboard widgets (order, size); screens the role can't open are marked;
    reset returns to the activity's default;
  - *forms*: modules declare a form's built-in fields (`"forms": {"product": {"label", "fields":
    [{"key", "label", "locked"?, "hidden"?}]}}`); a layout arranges built-in and custom fields in
    sections and hides fields (not locked or required ones). Fields placed nowhere go to the first
    (built-in) or last (custom) section. Product, customer and supplier forms render through
    `RecordFormFields` (`src/framework/forms.tsx`);
  - *custom fields*: the phase 4 fields API, now behind `designer`; a key can't take a built-in
    field's. Customers and suppliers now accept and validate `extra` like products and sales.
  - Changes are written to the audit log.
- **Custom fields in reports**: every export of products, stock, sales, customers and suppliers
  has a column per custom field; `/reports/fields/{record}/{key}` counts records (and totals
  sales) by a field's value (the reports page's "حسب حقل مخصص" tab).
- **Fixed on the way**: the shared `Input`/`Select` dropped their styling whenever a page passed a
  `className` (price and phone inputs rendered unstyled); the API client failed on 204 responses
  labelled JSON (every "reset"/"delete" reported an error); batches' frontend definition was still
  "planned"; healthcare's clinic screens were attributed to `core`; standard roles only picked up a
  newly declared permission once something happened to sync them (in production the owner was
  refused the builder), so they now sync before the first permission check in each process.
- **Known gaps**: sale and sale-line forms (POS) don't use form layouts; layouts can't be copied between roles; activities don't yet
  declare per-role defaults (`roles` is empty everywhere, so a cashier starts from the activity's
  menu filtered by permissions).

## Phase 8 implementation notes (2026-11-12, #106)

Phase 8 goes activity by activity; each gets its menu and dashboard, per-role layouts, its
variants made real, and demo data that shows them.

**Retail (done)**
- **Layouts** (`activities/retail/activity.json`): a supermarket-worded menu, the dashboard, and
  the first per-role layouts (`roles`): the cashier gets the till, their invoices, shift and
  customers, with shift status, today's takings and recent sales on the dashboard; the
  storekeeper stock, products, transfers, receiving and suppliers; the accountant the treasury,
  customers, suppliers, sales, shifts, stock valuation and reports. Managers and admins get the
  activity's layout. Terms: an item is a «صنف».
- **POS retail variant (active): weighing-scale labels.** Scanning goes through
  `GET /pos/scan/{code}` (POS module, `service.scan`): a product barcode adds one; otherwise
  `emit("pos.scan")` lets the variant read the code. The retail variant decodes EAN-13 labels in
  the restricted range (prefixes 20–29): item code (the product's `scale_code`, a field the
  variant adds to products), then the weight in grams, or the price in piastres
  (`pos.scale_barcode`: `prefixes`, `item_digits`, `value` = weight|price). The cart takes
  fractional quantities (kg, three decimals); sales and stock already stored them.
- **Demo data**: retail's catalogue carries realistic prices (a catalogue item may be
  `(name, price)`; activities without a catalogue use retail's), packaged goods are sold by the
  piece, and a fresh counter (fruit, vegetables, cheese, meat) is sold by weight with scale codes.
- Tests: `system/backend/tests/test_retail.py`.

## Decision log (review of 2026-11-10)
Answers as given by the owner; *italics* = how this ADR applies them.

| # | Question | Answer |
|---|---|---|
| — | Where does the core ERP (contacts, catalog, inventory, sales, purchases, finance, POS, HR, reports) go? | A family/activity called **general**; modules can be customised by the activity they're part of: **modules have variants** |
| — | Goals check | Customise every activity; use a module from one activity in another; positions/roles unique per activity if wanted; every role/position has its own custom screen |
| — | Should an admin whose permission was removed still use it? | "Super admin can't access everything at once; instead he can act as any role: doctor, HR, etc." → #94 |
| 1 | Mandatory modules? | A **module/family development framework**; the family/activity structure defines the **default modules**; uninstalling them is allowed with a warning, a typed `delete` and awareness of the consequences |
| 2 | Several activities per workspace? | **One activity**, with base modules; the user can extend within the **family** or with modules from **other activities that have a variant** for this one |
| 3 | Who picks the variant? | **The activity; it can't be changed**, but each module's **settings** can |
| 4 | Positions vs roles | **Separate**; a position suggests roles |
| 5 | Several roles per user | Done from the **owner's workspace settings** |
| 6 | Screen customisation | **Full builder** |
| 7 | Who creates new activities/variants | **Pluggable**: community developers using the framework |
| 8 | "Local only" plugins | Developers **upload** modules (and can **sell** them; owners install), or **package privately** and install through the owner |
| 9 | Does `standard` fit every activity? | **Yes**, unless marked otherwise |
| 10 | Several roles: who switches? | **The owner assigns roles; the user switches between them** |
| 11 | Changing activity later | **Yes, with a guided conversion**, approved by the SaaS team (price may differ) |
| 12 | Data on uninstall | The owner chooses: delete now, or keep 30 days. Plus a **storage quota** the owner can see analysed, free or export |
| 13 | Builder scope | **Layouts + custom fields + forms** |
| 14 | Who uses the builder | **Owner + a `designer` permission** |
| 15 | Plans and families | **Paid per module** |
| 16 | Marketplace code on the cloud | **"Secure it"** → *isolation (ADR-007)* |
| 17 | Private packages | **Allowed anywhere**, secured with **custom smart restrictions and isolation** |
| 18 | Install permissions | **The owner approves the scopes** |
| 19 | Selling modules | **Through Mizan, revenue share** |
| 20 | Base price | **Base subscription** (platform + activity defaults) **+ add-ons** |
| 21 | Storage quota | **Database + files + kept data; warn at 80%, block uploads at 100%** |
| 22 | Module updates | **Owner always chooses** → *refined by #25* |
| 23 | Families and activities | **Every module has its activity**, a unique id and variants for other activities; a new workspace takes the required modules from any activity (**a compatible variant is a must**) |
| 24 | What is a family? | **Families group activities, for organising only**; `general` is inherited by all; an activity in one family may have a variant for an activity of another |
| 25 | Versions on the cloud | **Community modules: owner's choice; official: everyone on the latest** |
| 26 | Security fixes | **The owner decides, in settings** → *proposed default: automatic; Mizan can still pull a malicious module from the marketplace* |
| 27 | Third-party UI | **Screen builder only** |
| 28 | On-site and paid modules | Each module sold for a non-cloud install is exported as **one file with the instance id**: can't be reversed or installed elsewhere; installation is local, and works on the cloud too |
| 29 | First milestone | **A detailed plan about everything, including the developer portal** (this ADR) |
| 30 | The bug batch | **Finish it first**, then start this |
