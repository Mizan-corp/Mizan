import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Food & Beverage Process Manufacturing: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "food_manufacturing",
  activity: "food",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "fod", perm: "", module: "food_manufacturing", component: lazy(() => import("./FoodProcessingPage")) },
  ],
};

export default definition;
