import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// الترفيه والفعاليات والملاهي (Entertainment & Events): what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "events",
  activity: "entertainment",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "ent", perm: "", module: "events", component: lazy(() => import("./EntertainmentPage")) },
  ],
};

export default definition;
