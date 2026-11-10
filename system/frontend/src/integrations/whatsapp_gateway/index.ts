import type { ModuleDefinition } from "@app/framework/types";

// WhatsApp Business & Digital Receipt Dispatch: the routes, screens, widgets and navigation entries this module provides (ADR-006).
// Screens are still registered in App.tsx and lib/nav.ts until the framework renders them.
const definition: ModuleDefinition = {
  id: "whatsapp_gateway",
  activity: "general",
  kind: "integration",
  screens: {},
  widgets: {},
  nav: [],
};

export default definition;
