import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Professional Services: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "services",
  activity: "consulting",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "services", perm: "", module: "services", component: lazy(() => import("./ServicesConsultingPage")) },
  ],
};

export default definition;
