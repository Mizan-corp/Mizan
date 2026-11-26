import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Pharmaceutical & Chemical GMP Manufacturing: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "pharma_manufacturing",
  activity: "pharmaceuticals",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "phm", perm: "", module: "pharma_manufacturing", component: lazy(() => import("./PharmaGmpPage")) },
  ],
};

export default definition;
