import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// School & Education Management: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "school",
  activity: "school",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "school/students", perm: "", module: "school", component: lazy(() => import("./SchoolStudentsPage")) },
  ],
};

export default definition;
