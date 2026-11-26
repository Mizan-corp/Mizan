import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Real Estate & Property Management ERP: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "real_estate",
  activity: "property",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "rec", perm: "", module: "real_estate", component: lazy(() => import("./RealEstatePage")) },
  ],
};

export default definition;
