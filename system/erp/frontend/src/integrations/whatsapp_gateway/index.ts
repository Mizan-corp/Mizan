import { lazy } from "react";
import type { ModuleDefinition } from "@app/framework/types";

// WhatsApp Business & Digital Receipt Dispatch: what this module provides to the app (docs/MODULE_STANDARD.md). Routes are
// registered in App.tsx; menus come from the manifest's "screens" and widgets render by id
// on the role's dashboard (ADR-006 phase 5).
const definition: ModuleDefinition = {
  id: "whatsapp_gateway",
  activity: "general",
  kind: "integration",
  status: "active",
  screens: {},
  widgets: {},
  routes: [
    { path: "integrations/whatsapp", perm: "", module: "whatsapp_gateway", component: lazy(() => import("./WhatsAppGatewayPage")) },
  ],
};

export default definition;
