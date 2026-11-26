import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Energy & Power Generation Plant ERP: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "energy",
  activity: "energy",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "eng", perm: "", module: "energy", component: lazy(() => import("./EnergyPowerPlantPage")) },
  ],
};

export default definition;
