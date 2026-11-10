import type { ModuleDefinition } from "@app/framework/types";

// Kitchen Display System: the routes, screens, widgets and navigation entries this module provides (ADR-006).
// Screens are still registered in App.tsx and lib/nav.ts until the framework renders them.
const definition: ModuleDefinition = {
  id: "kitchen_display",
  activity: "restaurant",
  kind: "business",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
