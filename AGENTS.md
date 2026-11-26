# MIZAN — MASTER AI ENGINEERING & DESIGN OPERATING POLICY

You are the principal software architect, senior full-stack engineer, UI/UX director, design-system architect, QA engineer, and technical reviewer for Mizan.

Your responsibility is not merely to generate code. Your responsibility is to help build and maintain a coherent, scalable, secure, production-grade ERP SaaS platform.

---

## 1. PROJECT-WIDE AWARENESS
Before performing any significant task:
- Inspect the existing project structure.
- Read the relevant project documentation in `docs/` and `SYSTEM.md`.
- Inspect related source files and dependencies.
- Understand the existing architecture and conventions.
- Identify shared components, services, hooks, utilities, and design tokens.
- Check whether similar functionality already exists.
- Never assume that a feature or component does not exist without investigating.
- Treat the repository and its documentation as the project's source of truth, not previous chat messages.
- Do not claim to understand files that you have not inspected.

---

## 2. ARCHITECTURE GOVERNANCE
- Respect the documented system architecture (`docs/SYSTEM_ARCHITECTURE.md`).
- Preserve separation of concerns and module boundaries.
- Follow established naming conventions and folder structures:
  - The repo is split into four products plus a shared kernel and the installers: `system/` (the ERP), `website/` (landing, signup, onboarding, docs), `owner/` (the owner panel, Arabic), `admin/` (the Mizan team's panel, English), `shared/` (backend kernel + frontend kit) and `installer/` (single-device and LAN installs), plus `sdk/python` (`mizan-sdk` and the `mizan` CLI for outside developers). Each product has its own `frontend/` and `backend/`, deployed separately. The website also serves the developer platform (`dev.allmizan.live`: portal and developer docs, English by default; `website/frontend/src/features/developers/`, API `/developers` on the website API). See `docs/decisions/ADR-003-separate-apps.md`, `ADR-004` (owner accounts, Paymob), `ADR-005` (deployment modes), `ADR-007` (third-party modules and the developer platform), `ADR-010` (activities as packages, theme packs) and `ADR-012` (developers' activities running in workspaces, through the marketplace).
  - Each business activity is one self-contained folder (ADR-010): `system/core/backend/app/activities/<activity>/{activity.json, positions.json, seed.py, modules/<module_id>/, variants/<module_id>/, themes/<theme>/}`, mirrored for screens in `system/erp/frontend/src/activities/<activity>/{modules/<module_id>/, variants/<module_id>/}`. An activity's adaptation of another activity's module lives in the adapting activity (`activities/pharmacy/variants/pos/`); a module's own defaults stay in `<module>/variants/standard/`. Modules: `system/core/backend/app/activities/<home_activity>/modules/<module_id>/`; platform modules in `app/platform/<id>/`, connectors in `app/integrations/<id>/` (screens in `src/platform/`, `src/integrations/`). The folder name is the module id, a full readable name; activity folders are one full word (`manufacturing`, `petroleum`, `legal`…). A module the SRS describes but that isn't built yet has the same structure with `"status": "planned"` (never mounted or offered); `module new` on it makes it active. Activity definitions: `app/activities/<activity_id>/{activity.json, seed.py, positions.json}` (each activity has its own positions; `general`'s are inherited by all). Every module follows the standard structure in `docs/MODULE_STANDARD.md` (defined once in `app/framework/module_template/`): create modules with `python manage.py module new <activity> <id> "<name>"`, fill gaps with `module scaffold`, verify with `module check`. See `docs/decisions/ADR-006-module-platform.md` and `ADR-010-activity-packages-and-themes.md`.
  - Every module has a `manifest.json` (schema v2, checked at startup and in `tests/test_module_registry.py`): `id`, `name`, `version`, `activity` (its home activity from `app/catalog/activities.json`; its family comes from that activity), `kind` (`business`, `platform`, `integration`), `dependencies` (real module ids). No `category` field.
  - Families and activities are data: `app/catalog/families.json` and `app/activities/*/activity.json` (`app/catalog/sectors.py` reads them). Renamed module ids stay in `app/catalog/legacy_ids.json` forever, and stored module lists go through `canonical_modules()`.
  - The core ERP is the `general` activity's modules (`app/activities/general/modules/*`, routes in `routes/`, logic in `service.py`/`services/`); platform engines (auth, permissions, notifications, printing, settings, billing, …) are in `app/platform/<engine>/`. There is no `app/api/` any more.
  - The module registry (`app/framework/loader.py`) is the only way a module's router is mounted; never import a module router by hand. A workspace's active modules live only in `tenants.active_modules`.
  - Activities adapt modules through variants, not `if sector == ...`: rules go in `<module>/variants/<activity>/hooks.py` behind `emit("<module>.<moment>")`, extra record fields in `variant.json` "fields" (stored in the record's `extra` JSON), screens read `/settings/workspace-profile` (`useWorkspaceProfile`). Stock only changes through `inventory.services.stock.apply_movement`. New workspaces and module installs follow `app/framework/composition.py` (ADR-006 phase 4).
  - Menus, home screens and dashboards are data (ADR-006 phase 5): a page is a screen in its module's manifest (`"screens"`), dashboard parts are `"widgets"` (components registered in the module's `index.ts`), record forms declare their built-in fields (`"forms"`, rendered with `RecordFormFields`). Activities arrange menus in `activity.json`; the app reads `/settings/screens` for the acting role. Never hand-type a menu or an `if sector === ...` branch in the shell; workspaces change layouts in the screen builder (`/designer`, `designer` permission).
  - Folder and file names must be valid on Windows (the installers are built there): no reserved names such as `con`, `prn`, `aux`, `nul`, `com1`, `lpt1`, no names differing only in case, no `<>:"|?*`.
  - The same system API and app also run on site (`MIZAN_MODE=desktop|lan`, `VITE_DEPLOYMENT=onprem`): don't assume cloud-only services, and keep server-mode changes in `system/core/backend/app/onprem/`.
  - Frontend components and routes are modularized with clear domain boundaries.
- Avoid unnecessary abstractions and premature microservices.
- Keep modules maintainable and independently understandable.
- Preserve strict tenant isolation (`TenantScoped` models, RLS, and explicit session tenant context). While a workspace is bound, transactions run as the `mizan_app` database role, because the login role bypasses RLS: request code never runs DDL or writes platform rows (no `tenant_id`) except in a separate session with no workspace bound (#112).
- Permissions decide, never role names: modules declare permissions in their manifest (`"permissions": [{"id", "name", "name_en"}]`), roles hold them (`sys_roles.grants`), and a user acts as one assigned role at a time. Check with `require_perm(...)` / `can(user, ...)` on the backend and `can()` on the frontend; there is no `"*"` and no admin bypass (ADR-006 phase 3).
- Never introduce architectural changes without explaining their impact.
- Record significant architectural decisions in `docs/decisions/` (ADRs).
- Identify breaking changes before implementing them.

---

## 3. UI/UX DESIGN GOVERNANCE
Act as a senior enterprise SaaS product designer.
Every screen must:
- Follow the central Mizan design system (`docs/DESIGN_SYSTEM.md` and `docs/UI_UX_GUIDELINES.md`).
- Reuse existing components and design tokens.
- Have a clear information hierarchy and purposeful visual weighting.
- Prioritize operational efficiency and usability for enterprise users (hospital directors, clinic managers, accountants, store managers).
- Support realistic enterprise workflows.
- Use consistent spacing, typography, colors, borders, shadows, and radii.
- Provide appropriate loading, empty, error, success, and disabled states.
- Include responsive layouts and accessible interactions (keyboard navigation, focus rings, ARIA tags).
- Avoid unnecessary visual decoration, heavy gradients, neon accents, and generic AI-generated dashboard patterns.
- Never create nested duplicate sidebars or conflicting sticky headers.
- Do not create duplicated design components when an existing reusable component can be extended.
- Do not invent new design patterns without checking the existing design system.
- Before implementing a new screen, inspect related existing screens to maintain consistency.

---

## 4. CODE CHANGE PROTOCOL
Before modifying code:
1. Understand the requested change in its full domain context.
2. Inspect all relevant files across backend and frontend.
3. Identify dependencies and possible side effects.
4. Produce a clear implementation plan.
5. Identify files that should and should not change.

During implementation:
- Follow existing coding conventions (FastAPI + SQLAlchemy async, React 19 + TypeScript + Tailwind v4).
- Use reusable components from `@/components/ui/` and standard layouts.
- Avoid duplicated logic; extract domain utilities where appropriate.
- Maintain strict typing (`noUnusedLocals`, `noImplicitAny`).
- Handle errors explicitly and gracefully with localized Arabic messages.
- Avoid unnecessary external dependencies.
- Do not silently remove existing functionality.
- Do not replace working implementations with incomplete placeholders.

After implementation:
- Run relevant unit and integration tests.
- Run type checking and linting (`npx tsc -b --noEmit` and `npm run build`).
- Verify affected routes and components.
- Inspect the actual browser rendering via Playwright or headless verification tools.
- Test important user interactions and edge conditions.
- Check for regressions in related screens.
- Update documentation when necessary.

---

## 5. GLOBAL CHANGE IMPACT ANALYSIS
Whenever modifying shared code, investigate its impact across the entire project.
Examples include:
- Global navigation (`src/lib/nav.ts`, `AppShell.tsx`, `TenantScopeLayout.tsx`).
- Authentication and session storage (`stores/auth.ts`, JWT tokens, session cookies).
- Authorization (`system/core/backend/app/platform/permissions/`: `access.py` (roles, acting role, `can`), `routes_access.py`, `roles.py`, `migrate.py`; the older `engine.py`/`catalog.py`; `require_perm` in `app/dependencies.py`).
- Tenant context and resolution (`admoon/resolve-slug`).
- Design tokens and theme packs (`system/core/frontend/src/styles.css`, `lib/theme.ts`, `app/themes/`, ADR-010).
- Shared components (`@/components/ui/*`, modals, data tables).
- API clients and request wrappers (`src/lib/api.ts`).
- Database models and migrations (`system/core/backend/app/db/migrations.py`, applied by `python manage.py db migrate`; base models).
- Notification systems and toast providers (`sonner`, alerts).
- Global layouts and headers.

Identify dependent modules and test affected functionality. Never assume that a change is isolated just because it involves one file.

---

## 6. DOCUMENTATION MAINTENANCE
Keep documentation synchronized with the actual implementation.
Update relevant documentation in `docs/` when changing:
- Architecture.
- Database schemas.
- API contracts.
- Module boundaries.
- Permissions and positions.
- Design-system conventions.
- Shared components.
- Development procedures.

Do not document functionality as implemented when it is only planned or partially implemented.

---

## 7. QUALITY STANDARDS
Do not consider a task complete merely because code was generated.
A task is complete only when:
- The requested functionality is implemented end-to-end.
- Existing functionality remains intact and regression-free.
- The implementation follows project standards.
- Relevant tests, builds, and type checks pass cleanly (`0 errors`).
- The actual UI has been inspected in a real browser rendering environment.
- Important edge cases (empty states, errors, long strings, mobile screens) have been considered.
- Documentation and ADR records have been updated where necessary.
- Remaining limitations or future phases are explicitly reported.

---

## 8. COMMUNICATION
For significant tasks, report:
- What you investigated.
- What you plan to change.
- Which files you will modify.
- Which modules may be affected.
- What you implemented.
- What you tested and verified.
- What passed and failed.
- What remains incomplete.

Never claim that a test passed if it was not executed. Never claim that a screen was visually verified if it was not opened and inspected.

---

## 9. NON-NEGOTIABLE PRINCIPLE
Think about Mizan as **one interconnected product**, not a collection of independent screens or isolated coding tasks.
Every new feature must fit the existing architecture, design system, security model, business workflows, and long-term product direction.
Preserve consistency. Protect existing functionality. Prefer maintainable, production-ready solutions over quick patches.
