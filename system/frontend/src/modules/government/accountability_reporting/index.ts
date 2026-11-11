import type { ModuleDefinition } from "@app/framework/types";

// Audit and accountability reporting: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "accountability_reporting",
  activity: "government",
  kind: "business",
  status: "planned",
  screens: {},
  widgets: {},
};

export default definition;
