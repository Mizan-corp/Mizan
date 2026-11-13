import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Point of Sale (POS): what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "pos",
  activity: "general",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {
    "pos.shift_status": lazy(() => import("./widgets").then((m) => ({ default: m.ShiftStatus }))),
    "pos.recent_sales": lazy(() => import("./widgets").then((m) => ({ default: m.RecentSales }))),
  },
};

export default definition;
