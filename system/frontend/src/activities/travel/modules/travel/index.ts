import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Travel & Tourism Agency Management: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "travel",
  activity: "travel",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "travel", perm: "", module: "travel", component: lazy(() => import("./TravelTourismPage")) },
  ],
};

export default definition;
