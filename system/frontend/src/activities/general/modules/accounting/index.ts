import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// Accounting: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" (shown only where the module is
// active and the role holds the screen's permission) and widgets render by id on the role's
// dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "accounting",
  activity: "general",
  kind: "business",
  status: "active",
  screens: {
    "accounting.journal": lazy(() => import("./screens/JournalPage")),
    "accounting.accounts": lazy(() => import("./screens/AccountsPage")),
    "accounting.reports": lazy(() => import("./screens/ReportsPage")),
    "accounting.periods": lazy(() => import("./screens/PeriodsPage")),
  },
  widgets: {},
};

export default definition;
