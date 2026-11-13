# Mizan ERP — UI / UX Guidelines

## 1. Design Personality
- **Sophisticated & Calm:** Designed for professionals who spend 8-12 hours daily in the software. Clean, focused, high contrast, zero distracting animations.
- **Warm editorial:** the workspace's theme decides the colours (Mizan's default: oxblood `#651E2C`, deep merlot sidebar, warm ivory surfaces). Screens use design tokens only, so they follow any theme (see [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md)).
- **Information Density without Clutter:** Tabular data and ledger views present maximum relevant operational context while preserving whitespace and visual breathing room.

## 2. Navigation & Layout Hierarchy
- **Master Shell:** Mizan provides a top-level organization layout (`TenantScopeLayout` + `AppShell`).
- **No Double Sidebars:** Standalone domain modules must never inject their own full-height fixed sidebars. Instead, modules utilize embedded horizontal navigation strips, segmented tabs, and contextual action headers.
- **RTL-First Typography:** Native Arabic layout flow with Latin numeral tabular alignment (`.num font-mono`). The admin panel and the developer platform are English (LTR) by default; use logical properties (`ps-`, `me-`, `start-`) so layouts flip correctly, and isolate English ids inside Arabic text.

## 3. Mandatory Component Patterns
- **Empty States:** Clear explanatory message with an immediate, primary call to action button.
- **Loading States:** Subtle spinners or skeleton cards; never jarring page flashes.
- **Feedback & Confirmation:** Destructive actions (record merge, bed discharge, patient archive) require explicit double confirmation modal dialogs.
