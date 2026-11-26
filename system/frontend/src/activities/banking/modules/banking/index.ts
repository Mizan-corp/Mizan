import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// الأنظمة المصرفية والتمويل (Banking & Financial Institutions): what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "banking",
  activity: "banking",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "bnk", perm: "", module: "banking", component: lazy(() => import("./BankingPage")) },
  ],
};

export default definition;
