import type { ModuleDefinition } from "@app/framework/types";

// Patient Portal & Digital Services: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "patient_portal",
  activity: "healthcare",
  kind: "business",
  status: "planned",
  screens: {},
  widgets: {},
};

export default definition;
