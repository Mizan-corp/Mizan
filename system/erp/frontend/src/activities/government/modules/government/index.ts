import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// القطاع الحكومي والمنظمات غير الهادفة للربح (Government & NGOs): what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "government",
  activity: "government",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "gov", perm: "", module: "government", component: lazy(() => import("./GovernmentPage")) },
  ],
};

export default definition;
