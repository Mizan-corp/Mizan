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

## 7. Revision: public marketplace and developer platform (owner direction, 26 November 2026, 13:43)

The owner's direction: (a) a community marketplace on `allmizan.live` where developers publish and promote modules, business activities and website templates, with the main storefront made for business owners to browse freely; (b) `dev.allmizan.live` for everything developer-related plus documentation; (c) the SDK downloads locally and brings the CLI tools and the Studio with it; (d) developers have accounts, can contribute with friends (GitHub-managed), can publish to Mizan and customise from the site their module's images, description, price and their profile as a programmer or company. He also said money is tight and free options come first, so every paid item below is a decision, not an assumption.

### 7.1 What the repo already has (ADR-007, ADR-008, ADR-010, ADR-012)

| Wish | Already there | Source |
|---|---|---|
| Developer accounts, separate from owner accounts, with teams | Built: accounts, teams, handles | `platform/developers`, ADR-007 D5 |
| Signing and trust | Built: Ed25519 developer keys certified by Mizan, offline verification, revocation, countersignature `MZP1` on approval | ADR-007 D5, milestone 1 and 2 |
| Publish flow | Built: `.mzm` package submit, `in_review/approved/rejected/withdrawn`, reviewer note, delist and relist, install counts | `platform/marketplace/listings.py`, ADR-007 milestone 2 |
| Review console | Built: admin "Marketplace" page with scope diff, webhooks, permissions, theme colours and fonts | ADR-007 milestone 2 |
| Store inside the ERP | Built: store section in the module centre (browse, search, filter by kind, installed and update available), re-verifies before install | system API `/modules/store` |
| `dev.allmizan.live` | Reserved and routed: nginx already sends `allmizan.live` and `dev.allmizan.live` to the website app; ADR-007 D6 puts the portal, docs and SDK wheel there | `deploy/server/nginx.conf`, ADR-008 |
| SDK and CLI | Specified and partly built: `mizan-sdk` (`mizan login`, `module new`, `check`, `package`, `publish`; `mizan dev` later) | ADR-007 D6, `sdk/` |
| Kinds of listing | Modules and theme packs only. Developer activity packages wait for the second part of #107 | ADR-007 milestone 2 |
| Free only | Paid listings, revenue share and payouts are not built and wait for Paymob (#65) | ADR-007 |

### 7.2 What is missing

1. **A public storefront on `allmizan.live`.** The store exists only inside a logged-in ERP (`/modules/store`, needs `community.manage`). Business owners cannot browse it from the public site, and nothing is indexable.
2. **Listing pages as marketing pages:** images and screenshots, long description, categories, version history, reviews or ratings (later), install count, developer profile link.
3. **Listing kinds beyond modules and themes:** business activities (needs #107 part 2: running a developer's activity package in a workspace), website templates (Studio page sets and blocks as a package kind), layout, header, font and palette items from section 6.
4. **Developer self-service for listing content:** edit images, description and price on the site without a new package version. Today description and media come from the package manifest and the reviewer sees them only at submission. Needs a mutable "listing profile" separate from the immutable signed version, with its own light review for text and images.
5. **Developer profile pages:** person or company, avatar, bio, links, verified status, their listings.
6. **GitHub-managed collaboration.** Teams exist, but there is no GitHub link. Options: sign in with GitHub and map team members to a GitHub org or repo; publish from a GitHub Action using a scoped publish token. Nothing is built.
7. **The SDK installing the Studio locally.** The SDK today is a Python package with a CLI; the Community Studio (section 6) does not exist and has no local mode. `mizan dev` (a local Mizan with the module) is listed as later.
8. **Developer docs to match.** Docs are planned at `dev.allmizan.live/docs`; the older inaccurate articles on the website are to be replaced.
9. **Paid items, payouts, tax and developer verification.** Entirely absent (see 7.5).

### 7.3 Hosting and routing for the two hostnames

Both hosts already hit the same website web container and the website API (`nginx.conf`: one server block for `allmizan.live` and `dev.allmizan.live`; `/owner/` and `/admin/` panels on the apex). Implications:

| Concern | Proposal |
|---|---|
| Public marketplace | A section of the website app on the apex, for example `allmizan.live/marketplace/...`, reading a public, cache-friendly listings API (approved, listed items only, no auth). Server-rendered or pre-rendered for search engines. Free to run on the current homie server |
| Developer platform | Stays on the website app under the `dev.*` host rule: home, portal, docs, SDK download, team and listing management |
| Separate identities | Owner login and developer login must not share a session. Cookies stay host-scoped (no Domain attribute today), which already keeps `dev.` and the apex apart. Keep it that way |
| Storage | Listing images and screenshots need an upload path with type and size limits, scanning, and serving from Mizan's origin. The package bytes already live in `marketplace_versions` |
| CDN and cost | Cloudflare already fronts the tunnel; cacheable listing and image routes cost nothing extra. No new hosting needed for phases 1 to 3 |
| Install source | An owner installing from the public page lands in their workspace's module centre, which re-verifies signatures as today. The public page never installs anything itself |
| On-site servers | Cloud store installs on on-site servers are listed as "not yet" in ADR-007. Keep out of the first phases |

### 7.4 Developer workflow, end to end (target)

1. Developer signs up at `dev.allmizan.live`, optionally with GitHub; creates a profile (person or company) and a team; invites friends. GitHub repo link is optional metadata at first.
2. `pip install mizan-sdk` (or the later installer). The SDK brings the `mizan` CLI and, in a later phase, the local Studio (`mizan studio`) that runs against a local Mizan with demo data.
3. Build: `mizan module new`, edit, `mizan check`, `mizan package`. Hand-written modules and integrations follow ADR-007 scopes.
4. `mizan publish` (or a GitHub Action with a team publish token). A signed version goes to `in_review`.
5. In the portal the team edits the listing: images, description, category, price (free by default), profile. Text and images changes go through light review.
6. Approved: Mizan countersigns, the listing appears on the public marketplace and in the ERP store.
7. Owners browse publicly, pick one, install from their workspace.

### 7.4a Account-gated SDK download and CLI and Studio sign-in (owner addition, 13:43)

The owner wants the SDK download (CLI tools and Studio included) to require a developer sign-in first. Today ADR-007 D6 plans the SDK as a public PyPI package (`mizan-sdk`) and as a wheel served at `dev.allmizan.live`. Gating the download means the public PyPI route is not the primary channel. Proposal:

| Part | Proposal |
|---|---|
| Download | The signed-in developer gets the SDK from the portal on `dev.allmizan.live` (installer or wheel plus the Studio bundle). Anonymous requests get the sign-in page. Signed download URLs are short-lived and tied to the account, so shared links stop working |
| Honest limit | A download gate controls distribution, not secrecy: once downloaded the package can be copied. The real protection is at publish time (signatures, scopes, review), not at download. If the SDK source is to be open (GitHub), a gate adds little; decide whether the gate is for tracking, terms acceptance and support, or for confidentiality |
| CLI login | `mizan login` uses a device-code flow: the CLI shows a short code and a URL, the developer approves in the browser session on `dev.allmizan.live`, and the CLI receives a token. No password typed into the terminal |
| Tokens | Per-developer, per-machine tokens, scoped (read docs and templates, publish for a named team), expiring, revocable from the portal, stored in the OS keychain where available. Separate publish tokens for CI (GitHub Actions), limited to one team and to publish only |
| Studio (local) | The local Studio reads the same token. Without a valid token it starts in a limited offline mode (edit and validate, no publish, no account data). It never receives owner workspace sessions or customer data |
| Separation | Developer tokens only work on developer endpoints and the publish API. They never work against a workspace's ERP API. Owner sessions never work on `dev.*` |
| Updates | The CLI checks for updates against the portal and verifies the Mizan signature on SDK releases before installing them |
| Terms | Sign-in is the natural place to accept the developer terms and show the review and signing rules once |

Consequences: add device-code and token endpoints to the developer API (website API router), a token table with scopes and revocation, a download route with signed URLs, and CLI changes in `sdk/python`. No new hosting cost. Phase 3 of 7.6 carries this work, since it is where sign-in and tokens land; the SDK download page moves into phase 3 as "account-gated".

### 7.5 Pricing and payouts: decisions, not assumptions

Nothing here is decided. Facts: ADR-007 says paid listings wait for Paymob (#65); revenue share, payout schedule and developer verification are open questions in the ADR. The owner said money is tight and free comes first.

Free-first approach: launch with free listings only. The listing schema reserves `price` and `currency` fields set to free, so adding paid items later changes no listing format. Paid items need, at minimum: a payment provider contract, refund policy, tax handling, payout method and schedule, developer identity verification, and dispute handling. Each has legal and cost consequences. None is built or proposed for build now.

### 7.6 Phased plan (free to build and run)

| Phase | Deliverable | Cost | Depends on |
|---|---|---|---|
| 0 | Contract tests and route registry (section 5.5, steps 1 and 2); decide what the public listing API exposes | none | none |
| 1 | Public read-only marketplace for existing kinds (modules, themes): listing API without auth, listing page, search and filter, developer profile page, owner-facing "Install from your workspace" hand-off | none (current server) | existing review and listings |
| 2 | Listing profile editing for developers (images, description, categories, price field fixed to free), light review for text and images, profile pages editable | none | phase 1 |
| 3 | Developer docs on `dev.allmizan.live/docs` replacing the old articles; SDK download page; GitHub sign-in and publish token for Actions | none | phase 1 |
| 4 | New listing kinds: website templates, layout, header, font and palette items (section 6 catalog items) | none | section 6 steps 2 and 7 |
| 5 | Local Studio with the SDK (`mizan studio`, `mizan dev`) | none | section 6, Community Studio |
| 6 | Business activity listings | none | #107 part 2 |
| 7 | Paid listings, payouts, ratings, analytics | provider fees, legal | owner decision; Paymob (#65) |

### 7.7 Risks
- A public storefront makes review quality visible to customers. Do not list anything not approved; keep delist with reason.
- Mutable listing text and images next to immutable signed versions: keep them clearly separate so a developer cannot change what an install actually does by editing a description.
- User-uploaded images are an abuse and malware vector: type sniffing, size caps, re-encoding.
- GitHub integration adds a third party: use read-only scopes, never store tokens in the clear, and keep publishing authorised by Mizan's own signing keys, not by a GitHub identity alone.
- Running both hosts on one app is cheap but couples their deploys. Acceptable now; revisit if the developer platform grows.

### 7.8 Real open decisions for the owner
1. First public release: free listings only, with price shown as "free", and paid items postponed until a payment provider and payout terms are decided. This plan assumes yes.
2. Light review of listing text and images by Mizan staff for every edit at launch, or only for the first publish and any later change to price or name.
3. SDK download gate: confirm the purpose (tracking and terms, or confidentiality). If confidentiality, the SDK cannot also be published openly on PyPI or GitHub.
4. GitHub: optional sign-in and Action-based publish first (my default), or required for all developer accounts.

## 8. Revision: packaged artifacts only, source is never published (owner direction, 26 November 2026, 13:45)

The owner's rule: source is NEVER exported or published. Only packaged artifact files are published, one extension per kind: `.mzba` (Mizan business activity), `.mzmo` (Mizan module), and similar extensions for themes and templates.

### 8.1 Reconciling with the repo

Today the repo uses one extension, `.mzm`, for every kind (71 mentions across code and docs; `framework/package.py`). The kind is not in the extension; it is the manifest's `kind` field (`community`, `theme`, `activity`). The owner's naming makes the kind visible from the file name. Proposal:

| Kind | Extension (proposed) | Replaces | Manifest `kind` |
|---|---|---|---|
| Module | `.mzmo` | `.mzm` with `community` | `community` (unchanged) |
| Business activity | `.mzba` | `.mzm` with `activity` | `activity` |
| Theme / design set (font, palette, header, layout) | `.mzth` | `.mzm` with `theme` | `theme` |
| Website template | `.mzwt` | not yet a kind | `site_template` (new) |
| Module UI / layout item (section 6) | `.mzui` | not yet a kind | `module_ui` (new) |

The `.mzth`, `.mzwt` and `.mzui` names are my suggestions in the owner's pattern; he only named `.mzba` and `.mzmo`. They are a naming decision for him (section 8.6).

Reconciliation rules: the container format stays the same (zip, `manifest.json`, `SIGNATURE`, per-file SHA-256, Ed25519 developer signature, Mizan countersignature `MZP1`). The extension must match the manifest `kind`; a mismatch is rejected at upload and at install. `.mzm` stays readable for one transition period so existing packages and the 71 references keep working, then is dropped. Format version bumps from 1 to 2 for the new naming and for the compiled payload (8.3).

### 8.2 What is inside and what is excluded

Inside (all kinds): `manifest.json`, `SIGNATURE`, declared entities, screens, i18n, assets (images, fonts, icons), README and CHANGELOG for the listing, and for code modules a compiled server payload (8.3). Activities add `modules/`, `variants/`, `themes/`, `seed/` as data.

Excluded, enforced by the packager and checked again at upload: source code (`.py`, `.ts`, `.tsx`, `.js` outside the compiled payload), source maps, tests, `.git`, lockfiles, build scripts, environment files, keys and any file not on the allow-list. Today's allow-list (`ALLOWED` in `package.py`) already permits only JSON, images, fonts and text, so declarative packages contain no executable source. The compiled-payload exception is new and narrow.

Important distinction, to avoid overselling: a declarative module is data (entities, screens, settings). Mizan must read that data to run the module, and the owner's workspace holds it after install. That is configuration, not source, but it is not secret from Mizan or from workspaces that install it. Secrecy applies to the developer's source repository, which never leaves their machine or their GitHub.

### 8.3 Code modules as packaged, compiled artifacts

ADR-007 plans code modules as "the same package plus a server program" in a sandbox container. Under the owner's rule:
- The developer builds locally with `mizan package`. The SDK compiles the server program to a self-contained artifact (for example a WebAssembly module or a compiled bundle with no source and no source maps) and puts only that in `.mzmo`.
- Honest limit: compiled code can be reverse engineered with effort. The rule protects against casual source exposure and accidental publication; it is not strong copy protection. Real protection is legal terms, signing, and keeping valuable logic behind the developer's own server (ADR-007 D4 already supports that: the module calls the developer's API and receives signed webhooks).
- Decision for the owner: which compiled target to support first. WebAssembly gives a strong sandbox, portability and no native toolchain, which fits the free-first constraint better than per-module containers (gVisor or Firecracker need cluster resources that are not available now).

### 8.4 How this answers the SDK-gate confidentiality question (section 7.8, decision 3)

The gate is no longer needed to keep Mizan's own source secret, because the question the owner answered is about developers' source: it is never published, so nothing confidential sits in the marketplace. That leaves the download gate with two purposes only: accounts, terms and support, and token issue. Both are compatible with an open-source SDK. Recommendation: the SDK and CLI can be published openly (PyPI or GitHub) if the owner wants reach, with the account required for `mizan login`, publish tokens, the local Studio's online features and marketplace access. If the owner wants the SDK itself kept closed, that is a separate choice and the gate must stay. Decision for him in 8.6.

### 8.5 Impact on review, signing and sandboxing

| Area | Impact |
|---|---|
| Review | The reviewer cannot read source, so review changes from reading code to reading declared behaviour: manifest, scopes, new scope diff, webhook hosts, entities, screens, assets, and, for compiled payloads, an automated analysis (declared imports and host calls only, size and resource limits, no filesystem or network outside declared hosts) plus a sandboxed behavioural run against demo data. Manual review can no longer rely on code reading, so scopes and observed behaviour carry the weight. For the first compiled modules, require the developer to be a verified publisher and keep review manual |
| Signing | Unchanged in design. The developer's Ed25519 signature covers every file hash including the compiled payload; Mizan's `MZP1` countersignature is over item, version, hash and kind. Add the extension and format version to the signed fields so a package cannot be relabelled to another kind |
| Provenance | Add an optional build attestation: the SDK records tool version, source commit hash and build timestamp in the manifest. This lets a developer or Mizan prove which source produced the artifact without publishing it |
| Sandbox | Compiled code runs only in the sandbox, with no database credentials, an outbound allow-list, quotas, and only the scoped extension API. Until the sandbox exists, code modules stay off production (section 6.7 decision, unchanged) |
| Revocation | Unchanged: revoke the version or the developer key; workspaces fall back |
| Updates | New version means new artifact, new hashes, new review; scope increases require re-consent by the owner |
| Support | Without source, Mizan cannot debug a developer's module. Developers own support; the portal needs a vulnerability-report path and a "delist on critical issue" action, which exists |

### 8.6 Phase changes to sections 6 and 7
- Add to section 7.6 phase 0: new extensions and format version 2 in the packager and verifier, kind-extension match check, allow-list kept, `.mzm` read-only for a transition period.
- Phase 5 (local Studio and SDK) carries the compile step for code modules; code-module publishing stays gated by the sandbox.
- No change to the free-first position.

### 8.7 Real open decisions for the owner
1. Names for the other kinds: confirm or change `.mzth` (theme and design sets), `.mzwt` (website template), `.mzui` (module UI and layouts). Only `.mzba` and `.mzmo` were specified.
2. Keep reading old `.mzm` files for a transition period, or cut over at once (no third-party packages are known to exist yet, so cut-over is cheap).
3. SDK openness: publish the SDK and CLI openly with account-gated publishing (my recommendation), or keep the SDK closed and gated.
4. First compiled-code target (WebAssembly recommended for the free-first constraint), or keep community modules declarative only for the first release.

## 9. Open questions (consolidated, all unanswered)

Collected from sections 5 to 8 at the owner's request (26 November 2026, 13:47) so they can be decided later. Each has a default that applies if nothing is decided; no default has been approved. Nothing in this document has been implemented.

### Layers and Studio (from section 5)
1. **Two-layer model.** Activity layouts by SaaS admins plus workspace choices, with one shared Studio engine, or admin-only authoring first. Default: two layers, one engine, because the workspace and role layout storage already exists and one engine avoids two editors.
2. **First activity to prove it.** `retail` or the Wirya-style website business. Default: `retail`, the most complete activity with the most existing layout data; the website case is already covered by Site Studio.

### Owner choices and community authoring (from section 6)
3. **Community code modules on production.** Only after the sandbox exists, or earlier when reviewed and signed. Default: after the sandbox, because hand-written code on real workspaces without isolation is the highest risk in the plan.
4. **Review at launch.** Manual review of every submission, or automated checks plus spot review once a developer has an approved history. Default: manual for every submission at launch, then relax on track record; volume will be small and a mistake is costly.
5. **First owner chooser release.** Fonts and colours only, with layouts and headers later. Default: fonts and colours only, since they are pure data with the lowest risk and no new page structure.

### Marketplace and developer platform (from section 7)
6. **Paid listings.** Free listings only at launch, price shown as free, paid items later. Default: free only, because paid needs a payment provider, tax, payouts and developer verification, and the owner said money is tight.
7. **Review of listing text and images.** Every edit, or only the first publish and later changes to name or price. Default: every edit at launch, then relax; the public storefront shows these directly to customers.
8. **Purpose of the SDK download gate.** Tracking and terms, or confidentiality. Default: tracking, terms and token issue. Section 8.4 explains that publishing only packaged artifacts removes the confidentiality need, so the SDK can be open.
9. **GitHub.** Optional sign-in and publish from Actions first, or required for all developer accounts. Default: optional, so developers without GitHub are not excluded.

### Package formats and compiled code (from section 8)
10. **Names for the other kinds.** Confirm `.mzth` (theme and design sets), `.mzwt` (website template) and `.mzui` (module UI and layouts) next to the owner's `.mzmo` and `.mzba`. Default: these names, in the owner's pattern; only the first two were specified.
11. **Old `.mzm` files.** Transition period or immediate cut-over. Default: cut over at once, because no third-party packages are known to exist; revisit if any do.
12. **SDK openness.** Open SDK and CLI with login required for publishing, or a closed SDK. Default: open with gated publishing, for reach at no cost.
13. **First compiled-code target.** WebAssembly, or declarative-only community modules for the first release. Default: declarative-only first, then WebAssembly when the sandbox exists, because it matches the free-first constraint and the sandbox gate in question 3.

### Execution that follows this plan (not from the sections above)
14. **Studio on the live server.** Deploy the current branch (Studio in the same web image as the ERP, ERP session reused so no second login) to homie, then test with a test account. Default: deploy only after the owner says so; it needs his approval click in GitHub. Until then nothing from this plan or the Studio changes is live.

## 10. Migration progress log

| Step | Branch | Status |
|---|---|---|
| 1. Contract tests (every active manifest screen has a route in `App.tsx`; every active module has a frontend `index.ts`) | `feat/modular-step1-contracts` | Done locally: `system/frontend/src/framework/moduleContract.test.ts`, passes against the current tree (no behaviour change) |

## 11. Folder structure: current and proposed (Studio as a system module)

"System module" means: part of the ERP's own composition (declared in the platform tree, always on, not in the workspace's `active_modules` list, not shown in the module centre or the marketplace, cannot be uninstalled). It is not a user module and not a developer module. Backend manifests get `"kind": "system"` (new) with `"always_on": true`; the loader mounts it for every workspace and `require_module` is not applied to it, while `require_perm` still is.

### 11.1 Current (relevant parts)

```
shared/backend/app/
  core/ db/ middleware.py factory.py dependencies.py     core runtime
  framework/                                              loader, activation, layouts, screens, events, hooks, package
  catalog/                                                activity families, module ids
  platform/<id>/                                          auth, tenancy, permissions, settings, site, themes, marketplace, ...
  activities/<activity>/modules/<id>/                     business modules (general holds the shared ones)
  integrations/<id>/                                      connectors
  themes/                                                 palettes, fonts
system/frontend/src/
  App.tsx                                                 hand-written route list (78 routes)
  components/AppShell.tsx shell-parts.tsx ...             panel shell
  features/<page>/                                        dashboard, products, customers, settings, designer, modules, studio, ...
  activities/<activity>/modules/<id>/                     business module UI
  platform/<id>/  integrations/<id>/                      platform and connector UI
  framework/                                              registry.ts, types.ts, forms, widgets
system/frontend/studio*.html, vite.studio.config.ts       Studio's separate entries and build
shared/frontend/src/                                      styles.css tokens, kit, lib, stores
sdk/python/                                               mizan-sdk and CLI
admin/ owner/ website/                                    other apps
```

### 11.2 Proposed

```
shared/backend/app/
  core/ db/ middleware.py factory.py dependencies.py      unchanged
  framework/
    layouts/                                              layout schema, resolver, validators (step 3)
    packaging/                                            .mzmo/.mzba/... packer and verifier (section 8)
    (existing files stay; split only when touched)
  system/                                                 NEW: modules that are part of the ERP itself, always on
    studio/                                               manifest.json (kind: system), router, service, models, migrations, tests
    (later, one by one: settings, designer, modules centre moved here from platform/ and features/)
  platform/<id>/                                          unchanged for now (shared services)
  activities/<activity>/modules/<id>/                     unchanged (business modules)
  integrations/<id>/                                      unchanged
  catalog/ themes/                                        unchanged; catalog items (section 6.3) added under catalog/

system/frontend/src/
  App.tsx                                                 shrinks to: shell, auth guard, route table built from the registry
  shell/                                                  AppShell.tsx, shell-parts.tsx, variants/classic (the current look, unchanged)
  system/                                                 NEW: system modules' UI
    studio/                                               index.ts (ModuleDefinition + routes), pages and editor moved from features/studio
    dashboard/ settings/ designer/ modules/               moved from features/ in step 8
  activities/<activity>/modules/<id>/                     business module UI; index.ts now also declares routes
  platform/<id>/  integrations/<id>/                      as today, index.ts declares routes
  framework/registry.ts types.ts                          ModuleDefinition gains routes[], tabs[]
  features/                                               emptied by step 8, then removed (auth, tenant, users, archive, reports move to system/ or their business module)
  studio-entry/                                           the standalone Studio HTML entries and vite configs (studio.html, studio-preview.html, vite.studio.config.ts), kept only for the hosted standalone build

shared/frontend/src/                                      styles.css tokens, kit, lib, stores: unchanged
sdk/python/mizan_sdk/                                     adds packaging (.mz* build), device login, studio launcher (later phases)
docs/                                                     this plan, ADRs, MODULE_STANDARD.md updated for kind "system"
```

### 11.3 What moves where, by step

| Step | Move |
|---|---|
| 2 | Routes: out of `App.tsx` into each module's `index.ts`. Files stay where they are |
| 3 | New `framework/layouts/` (backend) and a layout resolver module (frontend). No file moves |
| 5 | `AppShell.tsx` and `shell-parts.tsx` into `shell/`, current look becomes `variants/classic` byte for byte |
| 7 | Studio: `features/studio/*` to `system/studio/`; backend `platform/site` Studio parts to `system/studio/` (public site routes stay in `platform/site`); manifest `kind: system`, `always_on: true`; hidden from module centre and marketplace |
| 8 | Remaining `features/*` pages to `system/*` (dashboard, settings, designer, modules centre) or into their business module (products to inventory, customers to contacts, suppliers to purchases) |
| 9 | Packaging code in `framework/packaging/`; SDK adds the `.mz*` builder |

Rules that stay true during every move: public URLs and API paths do not change; each step is a separate branch with tests; the old import path keeps working (a re-export) until the next step removes it.
| 2. Route registry: modules declare routes in `index.ts` (`ModuleDefinition.routes`), `App.tsx` builds them into the route table | `feat/modular-step2-routes` | Done for every route whose page lives in a module folder with an `index.ts` (about 60 routes across 40 modules). Routes whose pages still live in `features/` stay in `App.tsx` until step 8 moves them. Test `routeTable.test.ts` compares the full table (path, guard permission, required module) with `routeTable.baseline.json`, taken before the move. |

## 12. Decision: merge `shared/` into `system/` (owner direction, 26 November 2026, 13:57)

The owner decided there is no separate `shared/` folder: its contents move inside `system/`. This section records what that touches, the dependency direction, the risks and a safe order. No file has been moved yet.

### 12.1 What imports `shared/` today (checked in the repo)

| Consumer | How | Where it is wired |
|---|---|---|
| `system`, `owner`, `admin` backends | Python dependency `mizan-shared` (path `../../shared/backend`), import name `app` | each `pyproject.toml`, Dockerfiles, `manage.py`, `docker-compose.yml`, `ruff.toml`, `installer/server/mizan_server/runner.py` |
| `website` API | the same backend package | same |
| `system`, `owner`, `admin` frontends | alias `@/` to `shared/frontend/src` | `vite.config.ts`, `vitest.config.ts`, `tsconfig.json` in each app |
| `website` frontend | npm workspace member with `shared/frontend` | root `package.json`, `deploy/server/Dockerfile.web` (`-w shared/frontend -w system/frontend -w website/frontend`) |
| SDK and deploy tooling | paths into `shared/backend/app/framework` | `sdk/python/mizan_sdk/*`, `deploy/studio-test/package.py`, `.github/ci-deps.sh`, `.github/workflows/ci.yml` |
| Tests and docs | about 40 files reference `shared/` paths; 66 mentions in docs and `AGENTS.md` | across the repo |

### 12.2 Dependency direction

Before: `system`, `owner`, `admin`, `website` all point down to `shared`; `shared` imports nobody.

After the merge, the same direction must hold, or the owner panel and admin app would depend on the whole ERP. So `system/` is split inside, and the direction is:

```
system/core/      (was shared: runtime, framework, platform services, UI kit, tokens, API client)   <- imports nothing above
system/erp/       (ERP app: system_api, ERP shell, ERP pages, system modules such as Studio)        -> imports system/core
owner/ admin/ website/                                                                              -> import system/core ONLY, never system/erp
```

A test enforces it: files under `system/core/` import nothing from `system/erp/`, `owner/`, `admin/`, `website/`; files in `owner/`, `admin/`, `website/` import nothing from `system/erp/`. If the split is skipped and `shared` content sits next to the ERP app in one flat `system/`, owner, admin and website would import the ERP tree, which breaks that rule. I recommend the `core` / `erp` split.

### 12.3 Risks

| Risk | Why | Mitigation |
|---|---|---|
| Broken builds and CI | `shared/` is hard-coded in about 40 files including Dockerfiles, CI, npm workspaces, vite and tsconfig aliases | Do it in two mechanical steps (below); run the full CI, a Docker build of the API and web images, and the frontend builds of all four apps before any deploy |
| Python package identity | the dependency is named `mizan-shared` and imported as `app`. Renaming the import breaks every module and every installed `.mzm` (hooks and scopes reference module paths) | Keep the import name `app` unchanged. Only the folder moves; the distribution name may stay `mizan-shared` (or be renamed once, separately) |
| Git history loss | moving folders can hide blame | `git mv` in one commit with no content change, so history follows |
| Open branches | 8 feature branches touch `shared/` paths; a move causes conflicts | Merge or rebase them after the move; do it only when the owner agrees, or move and tell him which branches need a rebase |
| Production deploy | the deploy workflow, `Dockerfile.api` and `Dockerfile.web` use `shared/` paths | Change paths and image builds in the same commit, verify with a real CI build, and deploy only after approval, as for every deploy |
| Owner, admin, website reach into ERP code | if the split in 12.2 is skipped | enforced by the dependency test |
| Wasted effort ordering | moving files before steps 3 to 5 enlarges every later diff | Do the move as its own step, right after step 2, when the diff surface is smallest, and before layouts and shell work |
| Uploads, updates, build folders | `shared/backend/uploads`, `updates`, `build` are runtime or build artefacts inside `shared/` | Check each is git-ignored; move code only |

### 12.4 Safe order (each its own branch, tests green, no behaviour change)

1. **Dependency test first** (no move): check that nothing in `shared/` imports an app, and that `owner/`, `admin/`, `website/` import `shared/` only. This pins today's direction before touching paths.
2. **Move backend**: `shared/backend/*` to `system/core/backend/*` with `git mv`; update `pyproject.toml` path dependencies, Dockerfiles, `manage.py`, `ruff.toml`, `docker-compose.yml`, installer runner, SDK and CI. Import name `app` unchanged. Verify: backend test suite, API Docker build, installer smoke.
3. **Move frontend**: `shared/frontend/*` to `system/core/frontend/*`; update the `@/` alias in all four apps, tsconfigs, npm workspaces and `Dockerfile.web`. Verify: all four frontend builds, vitest suites, `Dockerfile.web` build, the Studio standalone build.
4. **Rename ERP app folders** into `system/erp/` (backend `system_api`, frontend app) in a separate step, because it moves the most files. Verify the same way.
5. Update docs (`AGENTS.md`, `MODULE_STANDARD.md`, this plan) and add the dependency test to CI.

### 12.5 Effect on the plan in sections 5 to 11

- Section 11's tree: every path under `shared/` reads as `system/core/` instead. `system/` has two children, `core/` and `erp/`; the system modules (Studio) live in `system/erp/` on the frontend and under `system/core/backend/app/system/` on the backend because every API mounts them.
- Migration step order: this move is inserted as step 2b, after step 2 and before step 3.
- The "who may import" rule: every app may import `system/core`; `system/core` imports no app; `owner`, `admin`, `website` never import `system/erp`.

### 12.6 Decisions for the owner

1. Confirm the `system/core` and `system/erp` split inside `system/` (recommended), instead of one flat `system/`.
2. Timing: do the move now before steps 3 to 5 (recommended, smallest diff), or after the layout work.
3. Branches: OK to rebase or merge the open feature branches around the move.
| 2b-1. Dependency-direction test (no files moved): shared imports no app; owner, admin, website never import the ERP API or ERP frontend | `feat/modular-step2b-dependency-test` | Done: `system/frontend/src/framework/dependencyDirection.test.ts`, passes on today's tree, and was checked to fail when a probe violation is added |
| 3. Layout schema v1: typed, versioned models for a stored role layout and for the `/settings/screens` response (`framework/layout_schema.py`) | `feat/modular-step3-layout-schema` | Done, additive only: nothing calls the models at request time. `tests/test_layout_schema.py` validates every activity's defaults and `resolve()` output against the schema (77 checks), plus rejects bad layouts |
| 4. Activity layouts as data: `layout.json` (`schema: 1`) next to `activity.json` holds `home`/`menu`/`dashboard`/`roles`; read by `catalog.layout_of()` and merged over `activity.json` | `feat/modular-step4-activity-layouts` | Done for retail and general (moved out of `activity.json`). Other activities unchanged and still work. Test compares all 37 activities' layout keys with `activity_layouts.baseline.json` (taken before the move), validates the files against the schema, and rejects a wrong schema version. `package.py` does not read these keys. |
| 2b-2. Move backend: `shared/backend` to `system/core/backend` (`git mv`, import name `app` unchanged) | `feat/modular-step2b-move-backend` | Two commits: the pure move, then path updates (Dockerfiles, pyproject, pytest.ini, CI, compose, manage.py, installer, deploy, tests). All four APIs import, schema tests pass, dependency test passes. Docker not available in the sandbox, so CI and Docker builds must confirm. |
| 2b-3. Move frontend: `shared/frontend` to `system/core/frontend` (`git mv`, then path updates: `@/` alias and CSS import in system, owner, admin, website; npm workspaces; lockfile; `Dockerfile.web`) | `feat/modular-step2b-move-frontend` | Done. All four frontends type-check and build; system vitest 61 files / 339 tests pass. `Dockerfile.web` and the Studio standalone build are checked by CI/Docker only (no Docker in the sandbox). |
| 2b-4. Move the ERP app: `system/backend` and `system/frontend` to `system/erp/backend` and `system/erp/frontend` (`git mv`, then path updates; `manage.py` gets an app base folder, `deploy/server/asgi.py` loads the ERP from `system/erp`) | `feat/modular-step2b-move-erp` | Done. All four APIs import, schema tests 80/80, frontend tsc clean, vite build OK, vitest 61 files / 339 tests pass. Docker builds and real pytest left to CI. Layout is now `system/core` (kernel), `system/erp` (ERP app); owner, admin, website import only `system/core`. |

> Update (26 Nov 2026): steps 2b-2 to 2b-4 are done. `shared/` no longer exists: the kernel is `system/core/{backend,frontend}` and the ERP is `system/erp/{backend,frontend}`. Sections above that mention `shared/` describe the state before the move.
