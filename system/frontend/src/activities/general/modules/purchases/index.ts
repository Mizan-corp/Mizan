import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Purchases & Procurement: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "purchases",
  activity: "general",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "purchases", perm: "purchases|finance", component: lazy(() => import("./PurchasesPage")) },
    { path: "purchases/suggestions", perm: "purchases|finance", component: lazy(() => import("./screens/SuggestionsPage")) },
    { path: "purchases/price-history", perm: "purchases|finance", component: lazy(() => import("./screens/PriceHistoryPage")) },
    { path: "purchases/:id", perm: "purchases|finance", component: lazy(() => import("./screens/PurchaseOrderPage")) },
  ],
};

export default definition;
