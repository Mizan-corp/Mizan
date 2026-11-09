---
name: implement-module
description: Procedure for scaffolding and implementing a new standalone business module in Mizan
---

# Implement Module Procedure

When tasked with implementing a new module (e.g., `HLT-02`, `HLT-03`, `POS-02`):

1. **Requirements & Domain Inspection:**
   - Read the relevant requirements in `docs/PRODUCT_REQUIREMENTS.md` and module-specific specs.
   - Inspect existing peer modules in `shared/backend/app/modules/` to reuse common structures.

2. **Scaffold Directory Structure:**
   - Create `shared/backend/app/modules/<activity>/<module_name>/` (backend) and `system/frontend/src/modules/<activity>/<module_name>/` (screens):
     - `backend/`: Routers, schemas, services, and models.
     - `frontend/`: Types, mockData, components, and root `index.tsx`.
     - `manifest.json`: Module metadata, permissions, and dependencies.
     - `README.md`: Operational overview.

3. **Domain Models & Seed Data:**
   - Define TypeScript interfaces in `frontend/types.ts`.
   - Provide realistic localized Arabic mock data in `frontend/mockData.ts` for instant preview and offline resilience.

4. **Component Implementation:**
   - Build focused, production-grade screens adhering to `docs/UI_UX_GUIDELINES.md` and `docs/DESIGN_SYSTEM.md`.
   - Ensure complete states: Loading, Empty, Active, Error.

5. **Integration & Navigation:**
   - Expose the module in `system/frontend/src/modules/healthcare_clinic/ClinicHealthcarePage.tsx` (or parent activity page).
   - Ensure clean routing without layout nesting.

6. **Verification & Testing:**
   - Run `npx tsc -b --noEmit` and `npm run build` in `frontend/`.
   - Navigate to the module via Playwright MCP, take a screenshot, and verify typography, colors, and layout.
   - Document completion in `docs/DEVELOPMENT_ROADMAP.md`.
