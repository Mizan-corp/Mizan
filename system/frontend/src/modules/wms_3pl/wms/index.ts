import type { ModuleDefinition } from "@app/framework/types";

// 3PL & Warehouse Management System: the routes, screens, widgets and navigation entries this module provides (ADR-006).
// Screens are still registered in App.tsx and lib/nav.ts until the framework renders them.
const definition: ModuleDefinition = {
  id: "wms",
  activity: "wms_3pl",
  kind: "business",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
