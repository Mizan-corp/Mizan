import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Law Firm & Legal Practice Management: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "law",
  activity: "legal",
  kind: "business",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "law", perm: "", module: "law", component: lazy(() => import("./LawPracticePage")) },
  ],
};

export default definition;
