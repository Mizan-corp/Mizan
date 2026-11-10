import type { ModuleDefinition } from "@app/framework/types";

// عمليات البترول والغاز واستخراج الطاقة (Oil & Gas ERP): the routes, screens, widgets and navigation entries this module provides (ADR-006).
// Screens are still registered in App.tsx and lib/nav.ts until the framework renders them.
const definition: ModuleDefinition = {
  id: "oil_gas",
  activity: "petroleum",
  kind: "business",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
