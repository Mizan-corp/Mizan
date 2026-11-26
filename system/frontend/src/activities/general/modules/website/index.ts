import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Website: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// declared here and built into the route table by App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "website",
  activity: "general",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [{ path: "website", perm: "site.manage", component: lazy(() => import("./WebsitePage")) }],
};

export default definition;
