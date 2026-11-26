import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Human Resources & Payroll: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "hr",
  activity: "general",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "hr", perm: "payroll", component: lazy(() => import("./HrPage")) },
    { path: "hr/payroll", perm: "payroll", component: lazy(() => import("./PayrollPage")) },
  ],
};

export default definition;
