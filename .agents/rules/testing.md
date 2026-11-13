# Testing & Regression Rules for Antigravity

- **Zero TypeScript Errors:** before finishing, `npx tsc -b --noEmit` in each frontend you changed (or `python manage.py lint`).
- **Production Bundle Verification:** `npm run build` (or `python manage.py build`).
- **Backend:** `python manage.py test backend` (system, website, owner, admin, installer and SDK suites); `test e2e` for the live API suite; `test browser` for Playwright flows across the four apps. CI runs all of them.
- **Browser Visual Inspection:** for UI tasks, open the route in a real browser (Playwright) and look at the screenshot before calling it done.
- **Honest Reporting:** Never claim a test passed or a screen rendered cleanly without executing the command or inspecting the screenshot.
