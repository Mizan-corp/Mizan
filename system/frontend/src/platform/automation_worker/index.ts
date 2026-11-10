import type { ModuleDefinition } from "@app/framework/types";

// Background Automation & Cron Worker: what this module provides to the app (docs/MODULE_STANDARD.md). Screens are
// still registered in App.tsx and lib/nav.ts until the framework renders them (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "automation_worker",
  activity: "general",
  kind: "platform",
  status: "active",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
