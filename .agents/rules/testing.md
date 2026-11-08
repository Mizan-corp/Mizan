# Testing & Regression Rules for Antigravity

- **Zero TypeScript Errors:** Before finishing a turn, run `npx tsc -b --noEmit` in `frontend/` to ensure zero compilation or type errors.
- **Production Bundle Verification:** Run `npm run build` to confirm tree-shaking, asset compilation, and chunk integrity.
- **Browser Visual Inspection:** For UI tasks, navigate to the target route using Playwright MCP and capture a screenshot into `.gemini/antigravity/brain/.../audit_screens/` to verify layout correctness.
- **Honest Reporting:** Never claim a test passed or a screen rendered cleanly without executing the command or inspecting the screenshot.
