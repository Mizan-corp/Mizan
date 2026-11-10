import type { ModuleDefinition } from "@app/framework/types";

// Guest Folio & Incidentals Room Posting: the routes, screens, widgets and navigation entries this module provides (ADR-006).
// Screens are still registered in App.tsx and lib/nav.ts until the framework renders them.
const definition: ModuleDefinition = {
  id: "billing_folio",
  activity: "hotel",
  kind: "business",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
