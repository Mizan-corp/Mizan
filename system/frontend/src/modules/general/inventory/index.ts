import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Inventory & Supply: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "inventory",
  activity: "general",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {
    "inventory.low_stock_count": lazy(() => import("./widgets").then((m) => ({ default: m.LowStockCount }))),
    "inventory.low_stock": lazy(() => import("./widgets").then((m) => ({ default: m.LowStock }))),
  },
};

export default definition;
