# Mizan ERP — UI / UX Guidelines

## 1. Design Personality
- **Sophisticated & Calm:** Designed for professionals who spend 8-12 hours daily in the software. Clean, focused, high contrast, zero distracting animations.
- **Clinical yet Humane:** Professional deep navy (`#0A2540`), classic indigo (`#1E3A8A`), restrained teal accents (`#0D9488`), and cool slate surfaces (`#F8FAFC`).
- **Information Density without Clutter:** Tabular data and ledger views present maximum relevant operational context while preserving whitespace and visual breathing room.

## 2. Navigation & Layout Hierarchy
- **Master Shell:** Mizan provides a top-level organization layout (`TenantScopeLayout` + `AppShell`).
- **No Double Sidebars:** Standalone domain modules must never inject their own full-height fixed sidebars. Instead, modules utilize embedded horizontal navigation strips, segmented tabs, and contextual action headers.
- **RTL-First Typography:** Native Arabic layout flow with Latin numeral tabular alignment (`.num font-mono`).

## 3. Mandatory Component Patterns
- **Empty States:** Clear explanatory message with an immediate, primary call to action button.
- **Loading States:** Subtle spinners or skeleton cards; never jarring page flashes.
- **Feedback & Confirmation:** Destructive actions (record merge, bed discharge, patient archive) require explicit double confirmation modal dialogs.
