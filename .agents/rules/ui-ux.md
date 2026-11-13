# UI / UX Rules for Antigravity

- **Warm editorial aesthetic:** the workspace's theme decides colours (Mizan's default: oxblood `#651E2C`, deep merlot sidebar, warm ivory surfaces); write tokens, never hex values, in app screens. No neon, no gradients on data, no generic AI dashboard templates (docs/DESIGN_SYSTEM.md, docs/ui-ux-kit/).
- **Consistent Icons:** Exclusively use `lucide-react`. Never use emojis in functional controls or status badges.
- **Complete States:** Every data table and list must handle:
  1. Loading state (skeleton or subtle spinner).
  2. Empty state (helpful graphic, explanation, and primary action button).
  3. Error state (localized error with retry action).
  4. Search/filter empty state ("لم يتم العثور على نتائج تطابق بحثك").
- **Visual Browser Verification:** Every new screen must be visually inspected via a Playwright screenshot to verify alignment, contrast, and layout balance, in light and dark mode where it matters, and on a phone width.
