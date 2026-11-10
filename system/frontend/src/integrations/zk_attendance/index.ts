import type { ModuleDefinition } from "@app/framework/types";

// Biometric Attendance & ZK Device Sync: the routes, screens, widgets and navigation entries this module provides (ADR-006).
// Screens are still registered in App.tsx and lib/nav.ts until the framework renders them.
const definition: ModuleDefinition = {
  id: "zk_attendance",
  activity: "general",
  kind: "integration",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
