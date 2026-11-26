# Mizan ERP — Engineering Standards & Development Practices

## 1. Codebase Hygiene & Typing
- **TypeScript:** Strict mode enabled. Zero tolerance for `any` where domain types exist. Enforce `noUnusedLocals: true` and `noUnusedParameters: true`.
- **Python:** Strict type annotations on all FastAPI route signatures, Pydantic schemas, and SQLAlchemy repository methods.
- **Async All the Way:** Use asynchronous database queries (`await session.execute(...)`) and non-blocking I/O throughout backend services.

## 2. Testing & Quality Assurance
- **Frontend Build & Typecheck:** Every commit must pass `npx tsc -b --noEmit` and `npm run build` with exit code 0.
- **Unit & Integration Tests:** `pytest` in backend; Vitest/Testing Library in frontend.
- **End-to-End Verification:** `python manage.py test e2e` (the live API suite) and `test browser` (Playwright flows across the four apps, `e2e/browser/`), both in CI; inspect changed screens in a real browser before calling them done.
- **One command for everything:** `python manage.py check` runs what CI runs except e2e; `test backend` covers the system, website, owner, admin, installer and SDK suites.
- **Models match migrations:** a model declares its migration's primary key and database defaults (`create_all` builds local, CI and on-site tables before migrations run).

## 3. Component Architecture
- Reusable UI primitives live in the shared kit: `system/core/frontend/src/components/ui.tsx` and `components/kit/` (imported as `@/components/…`).
- Domain module screens live in `system/erp/frontend/src/activities/<home_activity>/modules/<module_id>/`; their backend lives in `system/core/backend/app/activities/<home_activity>/modules/<module_id>/` (platform modules: `app/platform/`, connectors: `app/integrations/`, mirrored in `src/platform/`, `src/integrations/`). See ADR-006.
- Every module follows [`MODULE_STANDARD.md`](MODULE_STANDARD.md) (created with `python manage.py module new`, checked by `module check` and the registry tests): `index.ts` (its definition and widgets), `api.ts`, `screens/`, `components/`, and on the backend `manifest.json`, models, schemas, service, router, hooks, seed.
- **Shared contracts have one source:** the package and manifest validator (`app/framework/manifest.py`) is copied byte for byte into the SDK, and tests fail if they drift; built-in themes and the SDK's starter theme likewise.
