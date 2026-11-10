import type { ModuleDefinition } from "@app/framework/types";

// Medical Equipment & Maintenance Management: the routes, screens, widgets and navigation entries this module provides (ADR-006).
// Screens are still registered in App.tsx and lib/nav.ts until the framework renders them.
const definition: ModuleDefinition = {
  id: "equipment_maintenance",
  activity: "healthcare",
  kind: "business",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
