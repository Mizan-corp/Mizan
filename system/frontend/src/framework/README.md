# Framework (frontend)

The module runtime on the app side (ADR-006):

- `types.ts`: what a module provides (`ModuleDefinition`): screens, widgets, navigation.
- `registry.ts`: collects every module's `index.ts`.
- Planned (phase 5): the screen renderer for builder schemas, the role shell (home, navigation and
  dashboard from the active role), and variant resolution of screen ids. Until then `App.tsx` and
  `lib/nav.ts` register screens by hand.
