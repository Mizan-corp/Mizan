import type { ModuleDefinition } from "@app/framework/types";

// عمليات البترول والغاز واستخراج الطاقة (Oil & Gas ERP): what this module provides to the app (docs/MODULE_STANDARD.md). Screens are
// still registered in App.tsx and lib/nav.ts until the framework renders them (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "oil_gas",
  activity: "petroleum",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
