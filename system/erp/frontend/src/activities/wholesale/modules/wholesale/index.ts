import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Wholesale & Bulk Distribution: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "wholesale",
  activity: "wholesale",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "wholesale", perm: "", module: "wholesale", component: lazy(() => import("./WholesaleDistributionPage")) },
  ],
};

export default definition;
