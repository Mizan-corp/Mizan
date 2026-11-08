# UI / UX Rules for Antigravity

- **Enterprise Aesthetic:** Midnight Blue (`#0A2540`), Slate (`#F8FAFC`), and Teal (`#0D9488`). Never use neon colors, gradients on flat data, or generic AI dashboard templates.
- **Consistent Icons:** Exclusively use `lucide-react`. Never use emojis in functional controls or status badges.
- **Complete States:** Every data table and list must handle:
  1. Loading state (skeleton or subtle spinner).
  2. Empty state (helpful graphic, explanation, and primary action button).
  3. Error state (localized error with retry action).
  4. Search/filter empty state ("لم يتم العثور على نتائج تطابق بحثك").
- **Visual Browser Verification:** Every new screen must be visually inspected via Playwright screenshot to verify alignment, contrast, and layout balance.
