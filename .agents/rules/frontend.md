# Frontend Engineering Rules for Antigravity

- **Strict Type Checking:** `noUnusedLocals: true` and `noUnusedParameters: true` are enforced. Never leave unused imports, variables, or state hooks.
- **RTL First:** All user interfaces are natively Right-to-Left (Arabic). Ensure margin, padding, and flexbox alignment consider `dir="rtl"`.
- **Numeric Formatting:** All numbers, quantities, currency amounts (EGP), and dates must use the `.num` / `font-mono` class for tabular clarity.
- **No Double Sidebars:** Standalone modules rendered within Mizan's app shell must not render full-height fixed sidebars. Use integrated horizontal command headers, tabs, or drawers.
- **Verification Rule:** Always run `npx tsc -b --noEmit` and `npm run build` in `frontend/` before declaring any frontend task complete.
