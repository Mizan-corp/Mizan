---
name: design-screen
description: Procedure for designing and reviewing an enterprise screen in Mizan
---

# Design Screen Procedure

1. **Context & User Role:**
   - Identify who uses this screen (e.g., Hospital Director, Outpatient Nurse, Billing Specialist).
   - Determine the primary operational action.

2. **Visual Canon Adherence:**
   - Palette: Deep Navy (`#0A2540`), Royal Blue (`#1E3A8A`), Slate (`#F8FAFC`), White cards (`#FFFFFF`).
   - Fonts: Arabic RTL text with `.num font-mono` for all figures, dates, IDs, and financial metrics.
   - Icons: Lucide React only (no emojis).

3. **Layout & Shell Integration:**
   - Embed within Mizan's master layout without injecting duplicate fixed sidebars.
   - Use top executive command headers and segmented tab strips.

4. **Self-Review Checklist:**
   - [ ] No double scrollbars or horizontal overflow.
   - [ ] Contrast meets WCAG AA standards.
   - [ ] Empty state provides an immediate action button.
   - [ ] Modals have accessible close triggers (ESC, Backdrop, Cancel button).
   - [ ] Live visual verification performed via Playwright.
