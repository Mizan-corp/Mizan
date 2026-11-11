import type { ModuleDefinition } from "@app/framework/types";

// Night Audit & Hospitality Metrics: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "night_audit",
  activity: "hotel",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
};

export default definition;
