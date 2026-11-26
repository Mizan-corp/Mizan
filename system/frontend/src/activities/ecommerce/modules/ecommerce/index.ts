import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Omnichannel E-commerce & Fulfillment: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "ecommerce",
  activity: "ecommerce",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "ecommerce", perm: "", module: "ecommerce", component: lazy(() => import("./EcommerceHubPage")) },
  ],
};

export default definition;
