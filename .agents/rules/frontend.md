# Frontend Engineering Rules for Antigravity

- **Strict Type Checking:** `noUnusedLocals: true` and `noUnusedParameters: true` are enforced. Never leave unused imports, variables, or state hooks.
- **RTL First:** the ERP and owner panel are Arabic (RTL); the admin panel and the developer platform are English (LTR) by default. Use logical properties (`ps-`, `me-`, `start-`, `end-`) and flip directional icons (`rtl:-scale-x-100`); isolate English ids inside Arabic text (`dir="ltr"` + `inline-block`).
- **Tokens, never colours:** use the design tokens (`bg-background`, `text-foreground`, `bg-primary`…) so screens follow the workspace's theme (docs/DESIGN_SYSTEM.md).
- **Numeric Formatting:** numbers, quantities, EGP amounts and dates use `.num` (Western digits, tabular).
- **No Double Sidebars:** modules inside the app shell never render their own full-height sidebar; use headers, tabs or drawers.
- **Verification Rule:** in the app you changed (`system/`, `website/`, `owner/`, `admin/` `frontend/`): `npx tsc -b --noEmit` and `npm run build` (or `python manage.py build`) before declaring a frontend task complete.
