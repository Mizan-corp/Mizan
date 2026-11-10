import type { ModuleDefinition } from "@app/framework/types";

// Biometric Attendance & ZK Device Sync: what this module provides to the app (docs/MODULE_STANDARD.md). Screens are
// still registered in App.tsx and lib/nav.ts until the framework renders them (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "zk_attendance",
  activity: "general",
  kind: "integration",
  status: "active",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
