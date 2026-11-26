import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Reporting engine: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "reporting",
  activity: "general",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {
    "reporting.sales_today": lazy(() => import("./widgets").then((m) => ({ default: m.SalesToday }))),
    "reporting.sales_month": lazy(() => import("./widgets").then((m) => ({ default: m.SalesMonth }))),
    "reporting.sales_trend": lazy(() => import("./widgets").then((m) => ({ default: m.SalesTrend }))),
  },
};

export default definition;
