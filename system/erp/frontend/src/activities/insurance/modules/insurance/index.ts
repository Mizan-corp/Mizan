import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// إدارة التأمين وإعادة التأمين (Insurance ERP): what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "insurance",
  activity: "insurance",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "ins", perm: "", module: "insurance", component: lazy(() => import("./InsurancePage")) },
  ],
};

export default definition;
