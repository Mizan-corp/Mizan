import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Kitchen Display System: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "kitchen_display",
  activity: "restaurant",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "restaurant/kitchen", perm: "", module: "restaurant", component: lazy(() => import("./KitchenDisplayPage")) },
  ],
};

export default definition;
