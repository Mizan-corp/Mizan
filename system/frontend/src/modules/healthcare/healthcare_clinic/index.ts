import type { ModuleDefinition } from "@app/framework/types";

// Healthcare & Clinic/Hospital ERP: what this module provides to the app (docs/MODULE_STANDARD.md). Screens are
// still registered in App.tsx and lib/nav.ts until the framework renders them (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "healthcare_clinic",
  activity: "healthcare",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
