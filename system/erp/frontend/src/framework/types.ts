import type { ComponentType } from "react";

/** A module's kind (ADR-006): business modules, the platform's own, and connectors. */
export type ModuleKind = "business" | "platform" | "integration";

/** `planned`: described (SRS) and laid out, not built; not mounted or offered to workspaces. */
export type ModuleStatus = "active" | "planned";

/**
 * What a module provides to the app (its `index.ts`). Menus come from the backend
 * (`/settings/screens`, built from the manifest's "screens"); `widgets` maps the widget ids the
 * manifest declares to the components a role's dashboard renders (ADR-006 phase 5).
 */
/** A page the module adds to the ERP route table (migration step 2). `perm` and `module` feed the
 * route guard exactly as the hand-written routes in App.tsx did. */
export interface ModuleRoute {
  path: string;
  perm: string;
  /** The module that must be active in the workspace (omit when the guard only checks `perm`). */
  module?: string;
  component: ComponentType;
}

export interface ModuleDefinition {
  id: string;
  activity: string;
  kind: ModuleKind;
  status: ModuleStatus;
  screens: Record<string, ComponentType>;
  widgets: Record<string, ComponentType>;
  /** Routes this module registers in the ERP; App.tsx builds the route table from every module's list. */
  routes?: ModuleRoute[];
}
