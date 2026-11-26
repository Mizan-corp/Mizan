# Modular core: map and proposal

Status: planning document. No code changed, nothing deployed. Written 26 November 2026 on `feat/studio-render-parity`. Everything in sections 1 to 3 was read from the repository at that commit. Section 4 is a proposal for the owner to decide on.

## 1. Map of the current structure

| Layer | Where | What it holds |
|---|---|---|
| Core runtime | `shared/backend/app/{core,db,middleware.py,factory.py,dependencies.py}` | Config, DB sessions, auth and CSRF middleware, app factory shared by every API |
| Framework | `shared/backend/app/framework/` | Module loader (`loader.py`), activation and presets (`activation.py`), events, hooks, fields, demo seeding |
| Catalog | `shared/backend/app/catalog/` | Activity families, canonical and legacy module ids |
| Platform modules | `shared/backend/app/platform/*` (auth, tenancy, permissions, settings, site, themes, marketplace, files, billing ...) | Things every workspace needs, one folder each |
| Business modules | `shared/backend/app/activities/<activity>/modules/<id>/` (`general` holds the shared ones: inventory, sales, pos, website, ...) | One folder per module: manifest, models, service, router, hooks, seed, migrations |
| Integrations | `shared/backend/app/integrations/*` | Connectors to outside systems |
| API apps | `system/backend` (ERP API), plus owner, admin and website apps | Thin entry points that call the factory |
| ERP frontend | `system/frontend/src/{App.tsx,components,features,activities,platform,framework}` | The panel: shell, pages, module UIs |
| Shared frontend | `shared/frontend/src` (`styles.css`, `components/kit`, `lib`, `stores`) | Design tokens, UI kit, API client, auth store |
| Studio | `system/frontend/src/features/studio` plus `platform/site` on the API side | Page builder (standalone entry `studio-preview.html`) |

Boundary rules already written down (`docs/MODULE_STANDARD.md`): a module never touches another module's tables, other modules call only its `service.py`, modules talk through events (`notify`) and hooks (`emit`), every table is tenant scoped.

Observed gaps in those boundaries:
- Frontend routes are still a single list in `App.tsx` (78 route lines). A module's UI is not self-registering.
- `features/` (dashboard, products, customers, settings, studio, ...) holds pages that are not modules, next to `activities/*/modules/*`. The line between "core UI" and "module UI" is by habit, not by rule.
- Studio's UI lives in `features/`, its API in `platform/site`, and its launcher in the `website` module. Three places, no single manifest.

## 2. How a module is registered, installed, enabled and rendered today

1. **Declared.** Backend: `manifest.json` in the module folder (id, name, kind, status, dependencies, permissions, screens, widgets, settings_schema). Frontend: `index.ts` returning a `ModuleDefinition` (screens, widgets).
2. **Discovered.** `framework/loader.py` scans `activities/*/modules`, `platform` and `integrations` for manifests, validates them, imports each module's `router` and keeps them in a registry. All active routers are mounted at startup (`factory.py`, `include_router`), for every workspace.
3. **Enabled per workspace.** Which modules a workspace uses is `tenants.active_modules` (`activation.get_active_modules`). Presets (retail, restaurant, ...) are bundles of module ids. `with_dependencies` pulls required modules in.
4. **Installed or toggled by the user.** Marketplace API `platform/marketplace/router.py`: list, `{module_id}/toggle`, `uninstall-preview`, `uninstall`, `presets/apply`, per-module settings. UI: `features/modules/ModulesPage.tsx`.
5. **Guarded.** Each module router depends on `require_module("<id>")`, which answers 403 when the module is not in the workspace's active list. Permissions are separate (`require_perm`).
6. **Rendered.** The panel menu and dashboard come from the backend for the acting role (`/settings/screens`, read by `useRoleScreens` in `lib/nav.ts`), built from manifests. Routes are matched in `App.tsx` with lazy imports. A menu entry with no route in `App.tsx` goes nowhere.
7. **Settings.** Each module can declare `settings_schema`; the Settings page lists modules and edits their values (`docs/module-settings-refactor.md`).

What this means in practice: "installing" a module is flipping an id in a list. The code of every module is always present in the build and mounted. There is no per-module package, version or lifecycle hook for install/uninstall beyond data retention rules.

## 3. Where the panel shell and look are defined

| Concern | File |
|---|---|
| Layout (sidebar, rail, top nav, topbar, mobile menu) | `system/frontend/src/components/AppShell.tsx`, `shell-parts.tsx` |
| App launcher between Mizan apps | `components/MizanAppLauncher.tsx` |
| Menu content | Backend `/settings/screens`, per role; icons mapped in `lib/nav.ts` |
| Design tokens (radius, shadows, colours, brand hue) | `shared/frontend/src/styles.css` (`:root` and `data-theme` blocks) |
| Workspace theme and brand hue | Theme pack in the auth store, applied by `lib/theme`; set by the tenant |
| UI kit | `shared/frontend/src/components/kit` and `components/ui.tsx` |
| Design rules | `docs/DESIGN_SYSTEM.md`, `docs/UI_UX_GUIDELINES.md` |

The look is therefore centralised (tokens, kit, shell). A module only supplies page content. That is why a new module looks native without custom styling, and why Studio, which has its own standalone entry and bundle, can feel like a separate app.

## 4. Proposed modular design

### Principle
A small, stable core. Everything else is a module that registers through one contract on both sides, and can be listed, enabled and rendered without editing core files.

### Core (always present, not switchable)
Auth and session, tenancy, permissions, events and hooks, module registry and activation, settings, files, themes and design tokens, the panel shell, and the Studio engine as a core service (page, theme and publish API plus the editor).

### Modules (switchable per workspace)
Inventory, sales, POS, accounting, HR, website data and orders, helpdesk, and so on. Modules use core services and each other only through `service.py`, events and hooks.

### Studio placement
Studio is a core service because the goal is that any workspace can build its site without code. It ships in the core web build, uses the ERP session, and has no catalog toggle. The `website` module keeps only site data (orders, published products, attributes) and a launcher. Modules that need pages (storefront, helpdesk request forms) consume Studio's API; Studio never imports them.

### One contract, two sides

| Today | Proposed |
|---|---|
| Routes listed by hand in `App.tsx` | Each module's `index.ts` also declares its routes (path, lazy component, permission); `App.tsx` builds routes from the registry |
| Menu from backend, route from frontend, two places that must agree | Manifest `screens` is the single source; a test fails when a screen has no route |
| Studio spread over `features/studio`, `platform/site`, `website` | One `studio` platform entry with its own manifest and `index.ts`, same folders as other platform modules |
| All routers mounted for everyone, guarded at call time | Unchanged at first (safe); later, unmount or lazy-load inactive modules |
| Install = flip an id | Add `on_enable` and `on_disable` hooks and a declared data-retention policy per module |

### Incremental migration path (each step shippable alone, with tests)
1. **Document and test the contract.** Add a test that every manifest screen has a frontend route and every active module has an `index.ts`. No behaviour change.
2. **Frontend route registry.** Move routes out of `App.tsx` into each module's `index.ts`, one module at a time, starting with low-risk ones (website, loyalty). Keep `App.tsx` as fallback until empty.
3. **Studio as a platform entry.** Add its manifest and `index.ts`; add the ERP navigation entry through the same menu mechanism; session reuse (already committed as 1ae5ecc2, not deployed).
4. **Move `features/*` pages into modules or platform entries** (products into inventory, customers into contacts) so `features/` disappears.
5. **Lifecycle hooks** for enable and disable, then per-module migrations (the standard already names `migrations/README.md`).
6. **Optional, later:** lazy mounting and separately versioned modules for the marketplace (ADR-007).

### Risks
- A large rewrite before production would block shipping. Each step above leaves the app working.
- Moving routes changes URLs only if paths change; keep every historical path.
- Visual changes to the shell are out of scope here. Any shell redesign needs a mockup and the owner's approval first.

### Open questions for the owner
1. Is the panel look itself in question (layout, density, menu style), or only how modules are handled? Section 3 shows where each is defined; a look change would be a separate mockup-first task.
2. Should disabling a module hide its data or only its screens? Today it only blocks API access and menu entries.
3. Is Studio's own bundle (separate HTML entry) acceptable, or should it open inside the ERP shell, as a page with the same sidebar? The second is a visual change and needs a mockup.

## 5. Revision: extensible hierarchy (owner direction, 26 November 2026, 13:28)

The owner's direction, as he wrote it: the platform must be extensible; the hierarchy is Workspace > Business Activity > a layout customised per activity (an app-like UI); or a developer studio for SaaS admins to build the native layouts of the business activities. He asked for the plan to be adjusted. This section does that. Both options are proposed as two layers of one system, not as alternatives.

### 5.1 What already exists (read from the repo)

| Piece | Where | State |
|---|---|---|
| Activity (business type) | `activities/<activity>/activity.json`, `variants/`, `positions.json`, `seed.py` | Built. An activity arranges which module screens appear in menus |
| Screen resolution | `framework/screens.py`, served by `/settings/screens` | Built. Resolves the menu, home and dashboard for the acting role: module manifests, then the activity, then role layout |
| Workspace layouts | `framework/layouts.py`, table `workspace_layouts` | Built. Per workspace: `role` layouts (home, menu, dashboard) and `form` layouts (record field sections) |
| Layout editor for workspace owners | `features/designer/DesignerPage.tsx` | Built, covers role screens and record forms only |
| Theme packs | `themes/`, `platform/themes`, applied by `lib/theme` | Built. Colours, fonts, brand hue per workspace |
| Shell | `AppShell.tsx` | Fixed layout (sidebar, rail or top nav, topbar). Not data-driven |

So two of the three levels already have data: the activity and the workspace. What is missing is the layout of the shell and the pages themselves as data, and a tool for platform staff to author the activity level.

### 5.2 Hierarchy and who owns each level

| Level | Owner | Controls | Stored as |
|---|---|---|---|
| Platform | Mizan | Core services, shell engine, kit, tokens, the module and widget catalog | Code |
| Business Activity | SaaS admins and developers | The default app: which modules, menu structure, home and dashboard per position, shell variant, page layouts of native screens, theme default | Versioned layout data shipped with the activity package |
| Workspace | Workspace owner | Overrides on top of the activity default: hide or reorder menu items, dashboard widgets, form fields, brand and theme | `workspace_layouts` rows (exists) |
| Role | Owner or manager | Home, menu, dashboard per role | `workspace_layouts` kind `role` (exists) |

Resolution order, most specific wins: role override, workspace override, activity default, module default. This is the same chain `screens.resolve` already follows; the proposal extends it from menus and dashboards to shell variant and page layouts.

### 5.3 The two layers together

**Layer A: activity layouts as declarative data.** A layout is JSON validated against a schema: shell variant (sidebar, rail, top nav, app-style tabs), menu tree, home composition, dashboard widget grid, and for each native screen a list of blocks (table, form, KPI, chart) bound to module data and permissions. The shell reads this data and renders it with the existing kit and tokens. No per-activity React code. A new activity layout is data plus, only when a new block type is needed, one new block in the core block library.

**Layer B: workspace overrides.** Same schema, stored per workspace, validated as a patch over the activity layout. Owners can hide, reorder and rename within what the activity and their permissions allow. Locked elements (required fields, permission-guarded screens) cannot be removed, as `layouts.py` already enforces for forms.

**Layer C: the developer studio for SaaS admins.** An admin-only tool that edits Layer A. It is the same editing engine as the Designer and Studio (block palette, inspector, preview), pointed at activity layouts instead of a workspace, with preview against demo data of that activity, versioning, draft and publish, and a validator that rejects layouts referencing missing modules or permissions. Publishing an activity layout version does not touch workspace overrides; overrides that no longer fit are reported and fall back to the activity default, never silently dropped.

### 5.4 Where Studio fits

There are two things called Studio and they should share one engine:
1. **Site Studio** (today's page builder): builds public website pages for a workspace. It stays a core service: always present, same ERP session, same tenant.
2. **Layout/App Studio** (new): builds app layouts for the panel. Same editor components (canvas, inspector, block library, draft and publish), different target. Admin version edits activity layouts; the owner version edits workspace overrides (the Designer grows into it).

Both live in one `studio` platform entry with one manifest, one nav entry in the ERP, and one saved-draft and publish model. The public-site renderer and the panel shell renderer are two renderers over the same block and schema ideas. This answers the "feels isolated" concern: Studio becomes the single place where anything visual is authored, inside the platform rather than beside it.

### 5.5 Migration steps (revised, each shippable alone)
1. Contract tests: every manifest screen has a route; every active module has an `index.ts` (no behaviour change).
2. Frontend route registry: routes move from `App.tsx` into module `index.ts` files.
3. Layout schema v1: describe what `/settings/screens` already returns (menu, home, dashboard) as a versioned JSON schema, with validators. No UI change; existing data validates against it.
4. Activity layouts as data: move each activity's menu and dashboard arrangement into schema files in its package. Start with `retail` and `general`.
5. Shell variants: the shell reads a variant key from the resolved layout. Ship the current look as `classic`, byte-for-byte the same. Any new variant needs a mockup and the owner's approval first.
6. Workspace override layer on the new schema (the Designer saves overrides of the same shape).
7. Admin layout studio (Layer C), behind a platform-admin permission, first as editor for menu, home and dashboard, then page blocks.
8. Studio unification: one `studio` manifest, ERP nav entry, shared draft and publish model, SSO (session reuse is already committed as 1ae5ecc2, not deployed).
9. Move `features/*` pages into modules; add enable and disable lifecycle hooks.
10. Later: lazy mounting and versioned, marketplace-distributed layouts (ADR-007).

### 5.6 Risks
- **Over-generic layout engine.** A schema that tries to describe every screen becomes a second UI framework. Mitigation: layouts only compose existing blocks and native screens; complex screens (POS, accounting ledger) stay coded and are placed, not rebuilt.
- **Breaking upgrades.** Activity layout changes can clash with workspace overrides. Mitigation: schema versions, override patches by stable ids, a fallback to the activity default, and a report listing affected workspaces before publish.
- **Permissions leaking through layout.** A layout must never grant a screen the role lacks. Mitigation: the resolver always intersects with permissions and active modules; tested.
- **Visual drift from the approved concept.** Shell variants and the layout studio change what users see. Mitigation: `classic` stays identical; mockup and approval before any new look.
- **Scope.** Steps 3 to 7 are a multi-week effort. Mitigation: each step ships alone and the first four add no visible change.
- **Admin tool security.** The layout studio is a high-privilege editor. Mitigation: platform-admin only, audit log, draft and publish, no code execution in layouts.

### 5.7 Decisions needed from the owner
1. Approve the two-layer model (activity layouts by admins, workspace overrides by owners), with one shared Studio engine. Or prefer admin-only authoring for now and postpone owner overrides beyond today's Designer.
2. Which activity is the first target to prove it: `retail` (most complete) or the Wirya-style website business?

## 6. Revision: roles, choice-based customisation and community authoring (owner direction, 26 November 2026, 13:33)

The owner's direction: (1) the ERP owner only chooses among layouts, headers, fonts and colours; (2) SaaS developers design those options in their Studio and the owner picks from them; (3) community developers get their own studio to tune the same things plus anything website-related, can design UI for modules, and can write modules and integrations by hand; (4) one module can have several listed pages or tabs in the ERP. This section replaces the "owner edits overrides freely" idea in section 5.3 with a choice-based model.

### 6.1 Roles

| Role | Does | Cannot |
|---|---|---|
| Workspace owner | Picks one option from each catalog the workspace is offered: layout, header, font pair, colour palette (and, per role, a menu preset). Stores only the choice ids and small parameters | Edit layout structure or write CSS |
| SaaS developer (Mizan staff) | Designs the options in the SaaS Studio: layouts, headers, font sets, palettes, activity defaults. Publishes them to the platform catalog | Bypass review of their own publish (second person or automated checks) |
| Community developer | Authors in a community Studio: the same option types (as listings), website templates and blocks, module UI (pages, tabs, widgets), and hand-written modules and integrations through the existing developer portal | Publish directly to workspaces; touch core or other modules' tables |

This is narrower than section 5.3: workspace-level edits become "selection plus bounded parameters". Fine-grained arrangement (form fields, role menus) that the Designer already offers stays as it is today and is not widened.

### 6.2 What exists that this builds on
- Third-party modules: `docs/decisions/ADR-007-third-party-modules.md`. Declarative modules and code modules, scopes, signed webhooks, developer teams and signing keys, review states (`in_review`, `approved`, `rejected`, `withdrawn`), Mizan countersignature, revocation, free marketplace listings (`platform/developers`, `platform/marketplace`). Code-module sandboxing in containers is planned, not built.
- Themes and fonts: `themes/` palettes and font folders, activity theme packs (ADR-010).
- Several pages per module: already supported. A manifest's `screens` is a list; POS declares `/pos`, `/sales` and `/shifts`. What is missing is tabs inside one page and a declared page hierarchy.

### 6.3 What it means for the layout schema
Make everything a **catalog item** with an id, version, owner (platform or developer), status and a typed payload:

| Item type | Payload | Chosen by |
|---|---|---|
| `shell_layout` | Region arrangement (sidebar, rail, top nav, app tabs), slots for header and menu | Owner |
| `header` | Header composition from header blocks (logo, search, actions, user menu) | Owner |
| `font_set` | Heading and body families, sizes scale; self-hosted files only | Owner |
| `palette` | Token values (brand hue, surfaces, semantic colours) with contrast checks | Owner |
| `activity_app` | Activity default: modules, menu tree, home, dashboard, default choices above | Applied by activity |
| `module_ui` | A module's pages and tabs as layout data over its screens and widgets | Installed with module |

Workspace state becomes `{shell_layout: id@version, header: id@version, font_set: id@version, palette: id@version, per_role: {...}}`. Resolution stays role > workspace > activity > module default. Items are referenced by id and version; a removed or revoked item falls back to the activity default.

Pages and tabs: add to each screen entry `parent` (for grouping) and `tabs: [{id, label, route, permission, widget_or_component}]`. A module declares one or many top-level pages, each with optional tabs. The menu builder shows a module's pages as a group; the page header renders tabs. Permissions are per page and per tab; the resolver intersects with the role's permissions and the active modules, so a tab never shows what the role cannot open. Existing single-screen modules need no change.

### 6.4 Studios
One editor engine, three scopes, different permissions:

| Studio | Users | Edits | Output |
|---|---|---|---|
| SaaS Studio | Mizan developers | Platform catalog items, activity apps | Published catalog versions |
| Community Studio | Community developers | Own listings: option items, website templates and blocks, module UI | Submissions to review |
| Site Studio (today) | Workspace owner or staff | One workspace's public pages | The workspace's site |

Site Studio stays a core service on the ERP session. The other two live in the developer portal domain with their own login and team accounts, not in a customer workspace.

### 6.5 Publishing and review of community work
1. Author edits a draft in the Community Studio; preview runs against demo data in an isolated preview, never against a real workspace.
2. Submit creates an immutable version (hash, manifest, declared scopes), state `in_review`, as ADR-007 already does for modules.
3. Automated checks: schema validation, allowed block types only, asset type and size limits, font licence field, contrast checks for palettes, no external script or remote CSS, no inline code in declarative items, dependency and scope diff against the previous version.
4. Human review by Mizan for first submission and for any scope increase; later versions with no scope change can pass on automated checks plus spot review.
5. Approval: Mizan countersigns; item appears in the marketplace. Owners install or select it; installing shows the scopes in plain language.
6. Revocation: Mizan can revoke a version; workspaces fall back to the activity default and are notified.
7. Updates never change a workspace silently: a new version is offered, and the owner accepts it.

### 6.6 Security
- **Declarative items carry no code.** Layouts, headers, fonts and palettes are data. Rendered by core blocks. This removes script injection from the common case.
- **Hand-written modules and integrations** keep ADR-007's model: scopes, signed packages, webhook signing, revocation. Until container sandboxing exists, community code modules should stay disabled for production workspaces. This is the main gating decision in section 6.7.
- **Isolation:** community items never read workspace data at design time; preview uses demo data. At run time they read only through scoped APIs.
- **Assets:** fonts and images are uploaded, scanned, size-limited and served from Mizan's own origin. No remote font or CSS loading, which also protects owner privacy.
- **Website side:** community website blocks and templates render through the same sanitising path as Studio pages; no raw HTML or script blocks without a reviewed exception.
- **Accounts:** developer and customer identities are separate. Developer keys are per team and revocable. Every publish, approve and revoke is audit-logged.
- **Abuse and trust:** item payloads have size and complexity caps; ratings and verified-publisher status come later, not first.

### 6.7 Revised migration order
1. Contract tests and the route registry (as section 5.5 steps 1 and 2).
2. Catalog item schema v1 for `font_set`, `palette`, `header`, `shell_layout`, derived from what themes and the shell already do. The current look is item `classic`, unchanged.
3. Workspace selection model (choose among items) and the owner chooser UI. A mockup is required before any new UI.
4. Pages and tabs in the screen schema, with the menu and page header support. Backward compatible.
5. SaaS Studio for catalog items and activity apps, platform-admin only, draft and publish, second-person approval.
6. Studio unification: one editor engine, SSO for Site Studio (session reuse is committed as 1ae5ecc2 and not deployed).
7. Community Studio and submissions on top of the existing developer portal and review states; declarative items only.
8. Hand-written code modules for production workspaces, only after the container sandbox exists.

### 6.8 Real open decisions for the owner
1. Community code modules (hand-written, with their own backend logic): allowed on production workspaces only after the sandbox exists, or earlier for reviewed and signed modules? The default in this plan is after.
2. Who reviews community submissions at launch: Mizan staff manually for every submission, or automated checks plus spot review once a developer has an approved history?
3. Should a first release of the owner chooser cover fonts and colours only (lowest risk, data only), with layouts and headers following?
