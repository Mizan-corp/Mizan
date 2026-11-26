import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Hotel Property Management System (PMS): what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "hospitality",
  activity: "hotel",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "hospitality", perm: "", module: "hospitality", component: lazy(() => import("./HospitalityPmsPage")) },
  ],
};

export default definition;
