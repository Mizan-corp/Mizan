import type { ModuleDefinition } from "@app/framework/types";

// القطاع الحكومي والمنظمات غير الهادفة للربح (Government & NGOs): the routes, screens, widgets and navigation entries this module provides (ADR-006).
// Screens are still registered in App.tsx and lib/nav.ts until the framework renders them.
const definition: ModuleDefinition = {
  id: "government",
  activity: "government",
  kind: "business",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
