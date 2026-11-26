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
