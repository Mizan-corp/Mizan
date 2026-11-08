# Mizan ERP — Engineering Standards & Development Practices

## 1. Codebase Hygiene & Typing
- **TypeScript:** Strict mode enabled. Zero tolerance for `any` where domain types exist. Enforce `noUnusedLocals: true` and `noUnusedParameters: true`.
- **Python:** Strict type annotations on all FastAPI route signatures, Pydantic schemas, and SQLAlchemy repository methods.
- **Async All the Way:** Use asynchronous database queries (`await session.execute(...)`) and non-blocking I/O throughout backend services.

## 2. Testing & Quality Assurance
- **Frontend Build & Typecheck:** Every commit must pass `npx tsc -b --noEmit` and `npm run build` with exit code 0.
- **Unit & Integration Tests:** `pytest` in backend; Vitest/Testing Library in frontend.
- **End-to-End Verification:** Playwright MCP for browser-based visual verification of live routes, testing modals, navigation, and error boundaries.

## 3. Component Architecture
- Reusable UI primitives reside in `src/components/ui/`.
- Domain modules live in `backend/app/modules/<business_activity>/<module_name>/frontend/`.
- Every standalone module must provide:
  - `types.ts`: Clean domain data interfaces.
  - `mockData.ts`: Realistic localized seed data for offline preview and resilient fallback.
  - `components/`: Modular sub-views and interactive screens.
  - `index.tsx`: Root exported entrypoint.
