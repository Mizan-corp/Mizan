import type { ModuleDefinition } from "@app/framework/types";

// Batches and expiry (FEFO): what this module provides to the app (docs/MODULE_STANDARD.md). Screens are
// still registered in App.tsx and lib/nav.ts until the framework renders them (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "batches",
  activity: "pharmacy",
  kind: "business",
  status: "planned",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
